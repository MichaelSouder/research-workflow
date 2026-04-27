"""Run start/stop routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.datastore.base import User
from backend.models import StartBody
from backend.routers.auth import get_current_user
from backend.services import state

router = APIRouter(prefix="/api", tags=["run"])


@router.post("/run/start")
def start_run(user: Annotated[User, Depends(get_current_user)], body: StartBody | None = None):
    if state.is_running():
        raise HTTPException(status_code=409, detail="Pipeline already running.")
    if body and body.config_overrides:
        state.update_config(body.config_overrides, persist=False)
    env = state.get_config_for_pipeline()
    if not (env.get("QUALTRICS_API_TOKEN") and env.get("GRID_API_TOKEN")):
        missing = [k for k in ("QUALTRICS_API_TOKEN", "GRID_API_TOKEN") if not env.get(k)]
        raise HTTPException(
            status_code=400,
            detail=f"Missing required tokens: {', '.join(missing)}. Set them in Settings (and click Save), then try Start again.",
        )
    state.run_pipeline()
    return {"ok": True, "message": "Pipeline started."}


@router.post("/run/stop")
def stop_run(user: Annotated[User, Depends(get_current_user)]):
    ok, message = state.request_stop()
    if not ok:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}
