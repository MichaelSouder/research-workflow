"""Study-scoped distribution and mailing list API (qualtrics_util-style)."""

import threading
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.datastore.base import Datastore, STUDY_ROLE_EDITOR, STUDY_ROLE_VIEWER
from backend.routers.auth import get_current_user
from backend.routers.studies import get_datastore, require_study_access
from backend.services import state
from backend.datastore.base import User

router = APIRouter(prefix="/api", tags=["distribution"])


def _config_for_study(store: Datastore, study_id: str) -> dict[str, str]:
    """Merged study config (unmasked) for pipeline distribution module."""
    raw = store.get_study_config(study_id)
    return state.get_study_config_merged(raw)


@router.get("/studies/{study_id}/distribution/contacts")
def get_distribution_contacts(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List mailing list contacts (short form for table). Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config_dict = _config_for_study(store, study_id)
    try:
        from backend.pipeline.qualtrics_distribution import get_contact_list

        contacts = get_contact_list(config_dict, include_embedded=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    short = []
    for i, co in enumerate(contacts):
        emb = co.get("embeddedData") or {}
        short.append({
            "index": i,
            "id": co.get("id"),
            "firstName": co.get("firstName", ""),
            "lastName": co.get("lastName", ""),
            "name": f"{co.get('firstName', '')} {co.get('lastName', '')}".strip(),
            "email": co.get("email") or "",
            "phone": co.get("phone") or "",
            "embeddedData": emb,
            "scheduled": emb.get("SurveysSchedule"),
            "useSMS": emb.get("UseSMS"),
            "useEmail": emb.get("UseEmail"),
            "deleteUnsent": emb.get("DeleteUnsent"),
        })
    return {"contacts": short}


@router.get("/studies/{study_id}/distribution/check")
def get_distribution_check(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Validate survey, mailing list, message IDs. Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config_dict = _config_for_study(store, study_id)
    try:
        from backend.pipeline.qualtrics_distribution import check_ids

        result = check_ids(config_dict)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@router.get("/studies/{study_id}/distribution/status")
def get_distribution_status(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Return whether a send is in progress and last send result. Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    busy = state.get_distribution_busy(study_id)
    last = state.get_distribution_last_result(study_id)
    return {"busy": busy, "lastResult": last}


@router.get("/studies/{study_id}/distribution/distributions")
def get_distribution_list(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List email and SMS distributions for the survey/mailing list. Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config_dict = _config_for_study(store, study_id)
    try:
        from backend.pipeline.qualtrics_distribution import list_distributions

        return list_distributions(config_dict)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/studies/{study_id}/distribution/send-preview")
def get_distribution_send_preview(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Preview which contacts would receive a send (no actual send). Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config_dict = _config_for_study(store, study_id)
    try:
        from backend.pipeline.qualtrics_distribution import send_preview

        return send_preview(config_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/studies/{study_id}/distribution/send")
def post_distribution_send(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict[str, Any] | None = None,
):
    """Start sending distributions in background. Optional body: { limit, contactIndices, bypassTimeSlot }. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    if state.get_distribution_busy(study_id):
        raise HTTPException(status_code=409, detail="Distribution send already in progress.")
    config_dict = _config_for_study(store, study_id)
    limit = None
    contact_indices = None
    bypass_time_slot = False
    if body:
        if "limit" in body and body["limit"] is not None:
            if not isinstance(body["limit"], int) or body["limit"] < 1:
                raise HTTPException(status_code=400, detail="limit must be a positive integer.")
            limit = body["limit"]
        if "contactIndices" in body and body["contactIndices"] is not None:
            raw = body["contactIndices"]
            if not isinstance(raw, list):
                raise HTTPException(status_code=400, detail="contactIndices must be an array of integers.")
            contact_indices = []
            for x in raw:
                if not isinstance(x, int):
                    raise HTTPException(status_code=400, detail="contactIndices must be integers.")
                contact_indices.append(x)
        if body.get("bypassTimeSlot") is True:
            bypass_time_slot = True

    def run_send():
        try:
            from backend.pipeline.qualtrics_distribution import send_distributions

            result = send_distributions(
                config_dict,
                contact_indices=contact_indices,
                limit=limit,
                bypass_time_slot=bypass_time_slot,
            )
            state.set_distribution_last_result(study_id, result)
        except Exception as e:
            state.set_distribution_last_result(study_id, {"sent": 0, "errors": [str(e)]})
        finally:
            state.set_distribution_busy(study_id, False)

    state.set_distribution_busy(study_id, True)
    t = threading.Thread(target=run_send, daemon=True)
    t.start()
    return {"ok": True, "message": "Send started."}


@router.post("/studies/{study_id}/distribution/delete-unsent")
def post_distribution_delete_unsent(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict[str, Any] | None = None,
):
    """Delete unsent distributions. Body: { index?, contactId?, allUnsent? }. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    config_dict = _config_for_study(store, study_id)
    index = None
    contact_id = None
    all_unsent = False
    if body:
        if "index" in body and body["index"] is not None:
            if not isinstance(body["index"], int):
                raise HTTPException(status_code=400, detail="index must be an integer or null.")
            index = body["index"]
        if "contactId" in body and body["contactId"]:
            contact_id = str(body["contactId"]).strip()
        if body.get("allUnsent") is True:
            all_unsent = True
    selector_count = sum(
        1 for is_set in (index is not None, bool(contact_id), all_unsent) if is_set
    )
    if selector_count > 1:
        raise HTTPException(
            status_code=400,
            detail="Use only one of: index, contactId, or allUnsent.",
        )
    try:
        from backend.pipeline.qualtrics_distribution import delete_unsent

        result = delete_unsent(
            config_dict,
            contact_index=index,
            contact_id=contact_id or None,
            all_unsent=all_unsent,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True, "deleted": result.get("deleted", 0), "errors": result.get("errors", [])}


@router.post("/studies/{study_id}/distribution/export")
def post_distribution_export(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict[str, Any] | None = None,
):
    """Export survey responses (JSON or CSV). Body: { format?: "json"|"csv" }. Returns path. Requires viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config_dict = _config_for_study(store, study_id)
    file_format = "json"
    if body and body.get("format") in ("json", "csv"):
        file_format = body["format"]
    try:
        from backend.pipeline.qualtrics_distribution import export_surveys

        path = export_surveys(config_dict, file_format=file_format)
        return {"ok": True, "path": path, "format": file_format}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.patch("/studies/{study_id}/distribution/contacts/{contact_id}")
def patch_distribution_contact(
    study_id: str,
    contact_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict[str, Any],
):
    """Update contact embedded data. Body: { "embeddedData": { ... } }. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    embedded = body.get("embeddedData")
    if not isinstance(embedded, dict):
        raise HTTPException(status_code=400, detail="Body must include embeddedData object.")
    config_dict = _config_for_study(store, study_id)
    try:
        from backend.pipeline.qualtrics_distribution import update_embedded

        update_embedded(config_dict, contact_id=contact_id, update_fields=embedded)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True, "message": "Contact updated."}
