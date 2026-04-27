"""Box folders route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.datastore.base import User
from backend.routers.auth import get_current_user
from backend.services import state

router = APIRouter(prefix="/api", tags=["box"])


@router.get("/box/folders")
@router.get("/box/folders/")
def get_box_folders(user: Annotated[User, Depends(get_current_user)], root: str = "0"):
    try:
        return state.list_box_folders(root)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
