"""Studies and study-scoped config, status, run, users."""

import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.datastore.base import (
    DEFAULT_PIPELINE_ID,
    Datastore,
    User,
    STUDY_ROLE_ADMIN,
    STUDY_ROLE_EDITOR,
    STUDY_ROLE_VIEWER,
)
from backend.models import (
    AddStudyUserBody,
    ConfigUpdate,
    PipelineCreateBody,
    PipelineDefinitionBody,
    StartBody,
    StudyCreate,
    StudyUpdate,
)
from backend.pipeline_validation import validate_pipeline
from backend.roles import normalize_study_role_write, study_role_payload
from backend.routers.auth import get_current_user
from backend.services import scheduler as scheduler_service
from backend.services import state
from backend.services import pipeline_events as pipeline_events_service


def get_datastore(request: Request) -> Datastore:
    store = getattr(request.app.state, "datastore", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Datastore not configured")
    return store


def require_study_access(
    store: Datastore,
    user: User,
    study_id: str,
    min_role: str = STUDY_ROLE_VIEWER,
) -> str:
    """
    Return user's role for study if at least min_role. Raise 404 if no study, 403 if no access.
    Role order: viewer < editor < admin.
    Platform superusers have effective admin on every study (list/create studies via list_all_studies).
    """
    study = store.get_study(study_id)
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    if user.is_superuser:
        role = STUDY_ROLE_ADMIN
    else:
        role = store.get_user_study_role(user.id, study_id)
        if not role:
            raise HTTPException(status_code=403, detail="No access to this study")
    order = {STUDY_ROLE_VIEWER: 0, STUDY_ROLE_EDITOR: 1, STUDY_ROLE_ADMIN: 2}
    if order.get(role, -1) < order.get(min_role, 0):
        raise HTTPException(status_code=403, detail="Insufficient permission")
    return role


router = APIRouter(prefix="/api", tags=["studies"])


@router.get("/studies")
def list_studies(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List studies the current user has access to, with role. Superusers see all studies as admin."""
    if user.is_superuser:
        return {
            "studies": [
                {"id": s.id, "name": s.name, "description": s.description, **study_role_payload(STUDY_ROLE_ADMIN)}
                for s in store.list_all_studies()
            ]
        }
    pairs = store.list_studies_for_user(user.id)
    return {
        "studies": [
            {"id": s.id, "name": s.name, "description": s.description, **study_role_payload(role)}
            for s, role in pairs
        ]
    }


@router.get("/studies/dashboard")
def get_studies_dashboard(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List studies with run status and pipelines for the dashboard. Same access as list_studies."""
    if user.is_superuser:
        pairs = [(s, STUDY_ROLE_ADMIN) for s in store.list_all_studies()]
    else:
        pairs = store.list_studies_for_user(user.id)
    studies = []
    for s, role in pairs:
        status = state.get_status(s.id)
        pipelines = store.list_pipelines(s.id)
        studies.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            **study_role_payload(role),
            "status": status,
            "pipelines": [
                {"id": p.id, "name": p.name, "isDefault": p.is_default}
                for p in pipelines
            ],
        })
    return {"studies": studies}


@router.get("/studies/{study_id}")
def get_study(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Get study by id. Requires at least viewer."""
    role = require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    study = store.get_study(study_id)
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return {
        "id": study.id,
        "name": study.name,
        "description": study.description,
        **study_role_payload(role),
    }


@router.patch("/studies/{study_id}")
def patch_study(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: StudyUpdate,
):
    """Update study name and/or description. Requires admin."""
    require_study_access(store, user, study_id, STUDY_ROLE_ADMIN)
    if body.name is None and body.description is None:
        return {"ok": True, "message": "Nothing to update."}
    store.update_study(study_id, name=body.name, description=body.description)
    return {"ok": True, "message": "Study updated."}


@router.post("/studies")
def create_study(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: StudyCreate,
):
    """Create a new study. Caller must be admin of at least one study or a platform superuser; they become admin of the new study."""
    if not user.is_superuser:
        pairs = store.list_studies_for_user(user.id)
        if not any(role == STUDY_ROLE_ADMIN for _, role in pairs):
            raise HTTPException(status_code=403, detail="Only study admins can create studies.")
    study = store.create_study(name=body.name.strip(), description=(body.description or "").strip() or None)
    store.set_user_study_role(user.id, study.id, STUDY_ROLE_ADMIN)
    return {"ok": True, "study": {"id": study.id, "name": study.name, "description": study.description}}


@router.get("/studies/{study_id}/config")
def get_study_config(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    reveal_secrets: bool = False,
):
    """Get config for study. Requires at least viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    raw = store.get_study_config(study_id)
    return state.get_merged_config_from_study_config(raw, reveal_secrets=reveal_secrets)


@router.put("/studies/{study_id}/config")
def put_study_config(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: ConfigUpdate,
):
    """Update config for study. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    store.set_study_config(study_id, body.config)
    scheduler_service.refresh_schedule()
    return {"ok": True, "message": "Config updated." + (" Saved." if body.persist else "")}


@router.get("/studies/{study_id}/pipelines")
def list_study_pipelines(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List pipelines for the study. Returns at least one (default) if none saved."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    pipelines = store.list_pipelines(study_id)
    return {
        "pipelines": [
            {"id": p.id, "name": p.name, "isDefault": p.is_default}
            for p in pipelines
        ]
    }


@router.get("/studies/{study_id}/pipelines/stream")
async def stream_study_pipeline_events(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    pipeline_id: str | None = None,
):
    """SSE stream of pipeline create/update/delete events for this study. Optional pipeline_id to filter."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)

    async def event_stream():
        async for payload in pipeline_events_service.subscribe(study_id, pipeline_id):
            yield f"data: {json.dumps(payload)}\n\n"

    async def body_gen():
        async for chunk in event_stream():
            yield chunk.encode("utf-8")

    return StreamingResponse(
        body_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store, no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/studies/{study_id}/pipelines/{pipeline_id}")
def get_study_pipeline(
    study_id: str,
    pipeline_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Get full pipeline definition (nodes, edges). 404 if not found."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    pipeline = store.get_pipeline(study_id, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "isDefault": pipeline.is_default,
        "nodes": pipeline.nodes,
        "edges": pipeline.edges,
    }


@router.put("/studies/{study_id}/pipelines/{pipeline_id}")
def put_study_pipeline(
    study_id: str,
    pipeline_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: PipelineDefinitionBody,
):
    """Create or update a pipeline. Requires editor. Validates DAG and node types."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    if pipeline_id == DEFAULT_PIPELINE_ID:
        raise HTTPException(status_code=400, detail="Cannot overwrite the default pipeline id. Create a new pipeline or use another id.")
    try:
        validate_pipeline(body.nodes, body.edges)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.set_pipeline(
        study_id,
        pipeline_id,
        body.name,
        body.is_default,
        body.nodes,
        body.edges,
    )
    pipeline_events_service.publish(
        study_id,
        pipeline_id,
        "updated",
        {"name": body.name, "nodes": body.nodes, "edges": body.edges},
    )
    return {"ok": True, "id": pipeline_id, "message": "Pipeline saved."}


@router.post("/studies/{study_id}/pipelines")
def post_study_pipeline(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: PipelineCreateBody,
):
    """Create a new pipeline. Requires editor. Returns pipeline id."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    nodes = body.nodes if body.nodes is not None else []
    edges = body.edges if body.edges is not None else []
    try:
        validate_pipeline(nodes, edges)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    pipeline_id = store.create_pipeline(
        study_id,
        body.name,
        body.is_default,
        nodes,
        edges,
    )
    pipeline = store.get_pipeline(study_id, pipeline_id)
    if pipeline:
        pipeline_events_service.publish(
            study_id,
            pipeline_id,
            "created",
            {"name": pipeline.name, "nodes": pipeline.nodes, "edges": pipeline.edges},
        )
    return {"ok": True, "id": pipeline_id, "message": "Pipeline created."}


@router.delete("/studies/{study_id}/pipelines/{pipeline_id}")
def delete_study_pipeline(
    study_id: str,
    pipeline_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Delete a pipeline. If it was default, another pipeline becomes default (or use built-in). Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    if pipeline_id == DEFAULT_PIPELINE_ID:
        raise HTTPException(status_code=400, detail="Cannot delete the default pipeline.")
    existing = store.get_pipeline(study_id, pipeline_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    was_default = existing.is_default
    store.delete_pipeline(study_id, pipeline_id)
    pipeline_events_service.publish(study_id, pipeline_id, "deleted", {})
    if was_default:
        default_id = store.get_default_pipeline_id(study_id)
        return {"ok": True, "message": "Pipeline deleted. Default is now: " + (default_id or DEFAULT_PIPELINE_ID)}
    return {"ok": True, "message": "Pipeline deleted."}


@router.get("/studies/{study_id}/status")
def get_study_status(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    return state.get_status(study_id)


@router.get("/studies/{study_id}/activity")
def get_study_activity(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    return state.get_activity(study_id)


@router.get("/studies/{study_id}/errors")
def get_study_errors(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    return state.get_errors(study_id)


@router.post("/studies/{study_id}/run/start")
def start_study_run(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: StartBody | None = None,
):
    """Start pipeline for this study. Optional body.pipeline_id to run a specific pipeline; otherwise uses default."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    if state.is_running():
        raise HTTPException(status_code=409, detail="Pipeline already running.")
    config = store.get_study_config(study_id)
    overrides = (body and body.config_overrides) or {}
    if overrides:
        config = {**config, **{k: v for k, v in overrides.items() if v not in (None, "", "********")}}
    env = state.get_config_for_pipeline(config)
    if not (env.get("QUALTRICS_API_TOKEN") and env.get("GRID_API_TOKEN")):
        missing = [k for k in ("QUALTRICS_API_TOKEN", "GRID_API_TOKEN") if not env.get(k)]
        raise HTTPException(
            status_code=400,
            detail=f"Missing required tokens: {', '.join(missing)}. Set them in Connections, then try Start again.",
        )
    pipeline_id = (body and body.pipeline_id) or store.get_default_pipeline_id(study_id) or DEFAULT_PIPELINE_ID
    pipeline = store.get_pipeline(study_id, pipeline_id)
    step_order = None
    step_types = None
    if pipeline:
        try:
            step_order = validate_pipeline(pipeline.nodes, pipeline.edges)
        except ValueError:
            step_order = [n.get("id") for n in pipeline.nodes if n.get("id")]
        if step_order and pipeline.nodes:
            node_by_id = {n.get("id"): n for n in pipeline.nodes if n.get("id")}
            # Use node id as component id when type is "stage" (default pipeline); else use type (e.g. qualtrics, process).
            step_types = []
            for sid in step_order:
                node = node_by_id.get(sid, {})
                t = node.get("type", "stage")
                step_types.append(sid if t == "stage" else t)
    state.run_pipeline(
        study_id=study_id,
        config_dict=config,
        datastore=store,
        step_order=step_order,
        step_types=step_types,
    )
    return {"ok": True, "message": "Pipeline started."}


@router.post("/studies/{study_id}/run/stop")
def stop_study_run(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Stop pipeline for this study. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    ok, message = state.request_stop(study_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@router.get("/studies/{study_id}/users")
def list_study_users(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List users and roles for study. Requires admin."""
    require_study_access(store, user, study_id, STUDY_ROLE_ADMIN)
    pairs = store.list_study_users(study_id)
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                **study_role_payload(role),
            }
            for u, role in pairs
        ]
    }


@router.put("/studies/{study_id}/users")
def set_study_users(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict,
):
    """
    Set user roles for study. Body: { "users": [ {"user_id": "...", "role": "editor" }, ... ] }.
    Requires admin. Replaces existing assignments for this study.
    """
    require_study_access(store, user, study_id, STUDY_ROLE_ADMIN)
    users = body.get("users")
    if not isinstance(users, list):
        raise HTTPException(status_code=400, detail="Body must include 'users' array")
    # Get current users and remove all, then add new
    current = store.list_study_users(study_id)
    for u, _ in current:
        store.remove_user_study(u.id, study_id)
    for item in users:
        uid = item.get("user_id")
        raw = item.get("role") or "staff"
        try:
            canonical = normalize_study_role_write(str(raw))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if uid and store.get_user_by_id(uid):
            store.set_user_study_role(uid, study_id, canonical)
    return {"ok": True, "message": "Users updated."}


@router.post("/studies/{study_id}/users/add")
def add_study_user_by_email(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: AddStudyUserBody,
):
    """Add a user to the study by email. Requires admin. Role: admin or staff."""
    require_study_access(store, user, study_id, STUDY_ROLE_ADMIN)
    try:
        canonical = normalize_study_role_write(body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    target = store.get_user_by_email(body.email)
    if not target:
        raise HTTPException(status_code=404, detail="No user found with that email.")
    store.set_user_study_role(target.id, study_id, canonical)
    return {
        "ok": True,
        "user": {
            "id": target.id,
            "email": target.email,
            "name": target.name,
            **study_role_payload(canonical),
        },
    }


@router.get("/studies/{study_id}/box-config")
def get_study_box_config_status(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Return whether Box config is stored in DB for this study. Does not return secret content."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    configured = store.get_study_box_config(study_id) is not None
    return {"configured": configured}


@router.put("/studies/{study_id}/box-config")
def put_study_box_config(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    body: dict = Body(...),
):
    """Store Box JWT config JSON for the study. Body is the full Box config object. Requires editor."""
    require_study_access(store, user, study_id, STUDY_ROLE_EDITOR)
    try:
        raw = body if isinstance(body, dict) else {}
        config_json = json.dumps(raw) if raw else ""
        if config_json and not _is_valid_box_config(raw):
            raise HTTPException(
                status_code=400,
                detail="Invalid Box config: expected JWT config with boxAppSettings or clientID/clientSecret.",
            )
        store.set_study_box_config(study_id, config_json)
        return {"ok": True, "message": "Box config saved."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _is_valid_box_config(obj: dict) -> bool:
    """Basic validation that the object looks like a Box JWT config."""
    if not obj:
        return True
    if "boxAppSettings" in obj and isinstance(obj.get("boxAppSettings"), dict):
        return True
    if "clientID" in obj or "clientId" in obj:
        return True
    return False


@router.get("/studies/{study_id}/box/folders")
def get_study_box_folders(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    root: str = "0",
):
    """List Box folders for the study's config. Uses DB Box config if set. Requires at least viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config = store.get_study_config(study_id)
    try:
        return state.list_box_folders(root, config_dict=config, store=store, study_id=study_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/studies/{study_id}/grid/studies")
def get_study_grid_studies(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List Grid studies using the study's config. Requires at least viewer."""
    require_study_access(store, user, study_id, STUDY_ROLE_VIEWER)
    config = store.get_study_config(study_id)
    try:
        return state.list_grid_studies(config_dict=config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/studies/{study_id}")
def delete_study(
    study_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Delete study. Requires admin. Fails if a run is in progress for this study."""
    require_study_access(store, user, study_id, STUDY_ROLE_ADMIN)
    if state.is_running(study_id):
        raise HTTPException(
            status_code=409,
            detail="Cannot delete study while a pipeline run is in progress for it. Stop the run first.",
        )
    store.delete_study(study_id)
    return {"ok": True, "message": "Study deleted."}
