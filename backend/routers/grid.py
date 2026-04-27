"""Grid studies route."""

from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException

from backend.datastore.base import User
from backend.routers.auth import get_current_user
from backend.services import state

router = APIRouter(prefix="/api", tags=["grid"])


@router.get("/grid/studies")
@router.get("/grid/studies/")
def get_grid_studies(user: Annotated[User, Depends(get_current_user)]):
    try:
        return state.list_grid_studies()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502, detail=f"Grid API error: {getattr(e, 'response', e) or e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
