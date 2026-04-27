"""Config GET/PUT/PATCH routes.

Legacy endpoints are supported only when a user has exactly one study.
When a user has multiple studies, callers must use explicit study-scoped routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.datastore.base import User
from backend.models import ConfigUpdate
from backend.routers.auth import get_current_user
from backend.routers.studies import get_datastore
from backend.services import scheduler as scheduler_service
from backend.services import state

router = APIRouter(prefix="/api", tags=["config"])


def _resolve_legacy_study_id(store, user_id: str) -> str | None:
    """
    Resolve study id for legacy /api/config routes.
    - 0 studies: return None (caller may use in-memory fallback)
    - 1 study: return that study id
    - >1 studies: raise 400 to prevent writing/reading the wrong study credentials
    """
    pairs = store.list_studies_for_user(user_id)
    if not pairs:
        return None
    if len(pairs) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Legacy /api/config is ambiguous when you have multiple studies. "
                "Use /api/studies/{study_id}/config instead."
            ),
        )
    return pairs[0][0].id


@router.get("/config")
def get_config(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[object, Depends(get_datastore)],
    reveal_secrets: bool = False,
):
    study_id = _resolve_legacy_study_id(store, user.id) if store else None
    raw = store.get_study_config(study_id) if study_id else None
    if raw is not None:
        return state.get_merged_config_from_study_config(raw, reveal_secrets=reveal_secrets)
    return state.get_merged_config(reveal_secrets=reveal_secrets)


@router.put("/config")
def put_config(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[object, Depends(get_datastore)],
    body: ConfigUpdate,
):
    study_id = _resolve_legacy_study_id(store, user.id) if store else None
    if study_id:
        config = {**store.get_study_config(study_id), **body.config}
        store.set_study_config(study_id, config)
        scheduler_service.refresh_schedule()
        return {"ok": True, "message": "Config updated."}
    state.update_config(body.config, persist=False)
    scheduler_service.refresh_schedule()
    return {"ok": True, "message": "Config updated (no study; in-memory only)."}


@router.patch("/config")
def patch_config(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[object, Depends(get_datastore)],
    body: ConfigUpdate,
):
    return put_config(user, store, body)
