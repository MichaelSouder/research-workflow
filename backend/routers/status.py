"""Status, activity, and errors routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.datastore.base import User
from backend.routers.auth import get_current_user
from backend.services import state

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
def get_status_route(user: Annotated[User, Depends(get_current_user)]):
    return state.get_status()


@router.get("/activity")
def get_activity_route(user: Annotated[User, Depends(get_current_user)]):
    return state.get_activity()


@router.get("/errors")
def get_errors_route(user: Annotated[User, Depends(get_current_user)]):
    return state.get_errors()
