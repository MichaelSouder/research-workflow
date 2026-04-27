"""Platform superuser endpoints (user list, grant/revoke superuser, MCP keys, audit logs)."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.datastore.base import STUDY_ROLE_ADMIN, Datastore, User
from backend.mcp_key_hash import normalize_allowed_study_ids
from backend.passwords import MIN_PASSWORD_LEN, hash_password
from backend.roles import normalize_study_role_write
from backend.routers.auth import get_current_user
from backend.routers.studies import get_datastore

router = APIRouter(prefix="/api", tags=["admin"])


def _user_api_dict(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "isSuperuser": u.is_superuser,
        "hasPassword": bool(u.password_hash),
        "toolApiDataProxy": u.tool_api_data_proxy_enabled,
    }


def _require_superuser(store: Datastore, user: User) -> User:
    u = store.get_user_by_id(user.id)
    if not u or not u.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required.")
    return u


@router.get("/admin/users")
def list_platform_users(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """List all users (email, name, superuser flag). Superuser only."""
    _require_superuser(store, user)
    users = store.list_users()
    return {"users": [_user_api_dict(u) for u in users]}


class AdminCreateUserBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    name: str = Field(default="User", max_length=255)
    password: Optional[str] = None


@router.post("/admin/users")
def create_platform_user(
    body: AdminCreateUserBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Create a directory user (pending OAuth until first Google sign-in). Optional password enables email login."""
    _require_superuser(store, user)
    if body.password is not None and len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.",
        )
    pw_hash = hash_password(body.password) if body.password else None
    try:
        created = store.create_provisioned_user(
            body.email.strip(),
            (body.name or "").strip() or "User",
            password_hash=pw_hash,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    return {"ok": True, "user": _user_api_dict(created)}


class AdminPatchUserBody(BaseModel):
    is_superuser: Optional[bool] = None
    tool_api_data_proxy: Optional[bool] = None
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, min_length=3, max_length=255)
    password: Optional[str] = None
    clear_password: Optional[bool] = None


@router.patch("/admin/users/{target_user_id}")
def patch_platform_user(
    target_user_id: str,
    body: AdminPatchUserBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Update profile, superuser flag, and/or password. Superuser only."""
    _require_superuser(store, user)
    target = store.get_user_by_id(target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if all(
        v is None
        for v in (
            body.is_superuser,
            body.tool_api_data_proxy,
            body.name,
            body.email,
            body.password,
            body.clear_password,
        )
    ):
        raise HTTPException(status_code=400, detail="No changes provided.")
    if body.password is not None and body.clear_password:
        raise HTTPException(
            status_code=400,
            detail="Cannot set password and clear password in the same request.",
        )
    if body.password is not None and len(body.password) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LEN} characters.",
        )

    if body.email is not None or body.name is not None:
        try:
            store.update_user_profile(target_user_id, email=body.email, name=body.name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e

    if body.is_superuser is not None:
        store.set_user_superuser(target_user_id, body.is_superuser)

    if body.tool_api_data_proxy is not None:
        store.set_user_tool_api_data_proxy(target_user_id, body.tool_api_data_proxy)

    if body.clear_password:
        try:
            store.set_user_password_hash(target_user_id, None)
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e
    elif body.password is not None:
        try:
            store.set_user_password_hash(target_user_id, hash_password(body.password))
        except NotImplementedError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e

    updated = store.get_user_by_id(target_user_id)
    return {"ok": True, "user": _user_api_dict(updated) if updated else None}


@router.get("/admin/users/{target_user_id}")
def get_platform_user(
    target_user_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """User detail with study memberships. Superuser only."""
    _require_superuser(store, user)
    target = store.get_user_by_id(target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    studies_rows = store.list_studies_for_user(target_user_id)
    return {
        "user": _user_api_dict(target),
        "studies": [
            {
                "studyId": s.id,
                "name": s.name,
                "role": role,
            }
            for s, role in studies_rows
        ],
    }


class AdminUserStudyMembership(BaseModel):
    study_id: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=64)


class AdminSetUserStudiesBody(BaseModel):
    """Replace this user's study memberships. Roles use the same strings as study admin (admin, staff)."""

    memberships: list[AdminUserStudyMembership] = Field(default_factory=list)


@router.put("/admin/users/{target_user_id}/studies")
def put_platform_user_studies(
    target_user_id: str,
    body: AdminSetUserStudiesBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """
    Replace all study memberships for a user (superuser only).
    Each study must still have at least one admin after the change.
    """
    _require_superuser(store, user)
    target = store.get_user_by_id(target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    new_map: dict[str, str] = {}
    for m in body.memberships:
        sid = (m.study_id or "").strip()
        if not sid:
            continue
        st = store.get_study(sid)
        if not st:
            raise HTTPException(status_code=404, detail=f"Study not found: {sid}")
        try:
            new_map[sid] = normalize_study_role_write(m.role)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    old_pairs = store.list_studies_for_user(target_user_id)
    old_map = {s.id: role for s, role in old_pairs}

    affected = set(old_map.keys()) | set(new_map.keys())
    for sid in affected:
        new_role_target = new_map.get(sid)
        admins = 0
        for u, r in store.list_study_users(sid):
            if u.id == target_user_id:
                eff = new_role_target
                if eff is None:
                    continue
                r = eff
            if r == STUDY_ROLE_ADMIN:
                admins += 1
        if admins < 1:
            st = store.get_study(sid)
            label = st.name if st else sid
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Each study must keep at least one admin ({label}). "
                    "Assign another admin on that study before removing or demoting this user."
                ),
            )

    for s, _ in old_pairs:
        store.remove_user_study(target_user_id, s.id)
    for sid, role in new_map.items():
        store.set_user_study_role(target_user_id, sid, role)

    studies_rows = store.list_studies_for_user(target_user_id)
    return {
        "ok": True,
        "studies": [
            {
                "studyId": s.id,
                "name": s.name,
                "role": role,
            }
            for s, role in studies_rows
        ],
    }


@router.get("/admin/platform-summary")
def get_platform_summary(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Dashboard KPIs. Superuser only."""
    _require_superuser(store, user)
    stats = store.platform_dashboard_stats()
    return stats


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class CreateMcpApiKeyBody(BaseModel):
    name: str = Field(default="API key", min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    owner_user_id: str = Field(..., min_length=1, description="Human owner (user id); required.")
    expires_at: str = Field(..., min_length=1, description="ISO-8601 datetime; required.")
    allowed_study_ids: list[str] = Field(
        ...,
        min_length=1,
        description="At least one study id; keys are always study-scoped.",
    )


class PatchMcpApiKeyBody(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[str] = None  # ISO-8601; omit to leave unchanged
    clear_expires_at: bool = False  # rejected — expiry cannot be removed
    allowed_study_ids: Optional[list[str]] = None
    clear_allowed_study_ids: bool = False
    owner_user_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Set human owner (user id); required for Integrations zip when wrong user was chosen at create.",
    )


class PurgeInvocationLogsBody(BaseModel):
    older_than_days: int = Field(ge=1, le=3650, description="Delete rows older than this many days")


@router.get("/admin/mcp-tool-names")
def list_mcp_tool_names(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Sorted tool names for API key scope UI."""
    _require_superuser(store, user)
    from backend.routers import tool_api as tool_api_mod

    tool_api_mod._register_tools()
    return {"tools": sorted(tool_api_mod._TOOL_MAP.keys())}


@router.get("/admin/mcp-api-keys")
def list_mcp_api_keys(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    _require_superuser(store, user)
    keys = store.list_mcp_api_keys()
    return {
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "keyPrefix": k.key_prefix,
                "scopes": k.scopes,
                "allowedStudyIds": k.allowed_study_ids,
                "ownerUserId": k.owner_user_id,
                "createdAt": k.created_at.isoformat(),
                "revokedAt": k.revoked_at.isoformat() if k.revoked_at else None,
                "lastUsedAt": k.last_used_at.isoformat() if k.last_used_at else None,
                "expiresAt": k.expires_at.isoformat() if k.expires_at else None,
            }
            for k in keys
        ]
    }


@router.post("/admin/mcp-api-keys")
def create_mcp_api_key(
    body: CreateMcpApiKeyBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Create a key; plaintext `secret` is returned once (never stored). Only a hash is persisted."""
    _require_superuser(store, user)
    ou = store.get_user_by_id(body.owner_user_id.strip())
    if not ou:
        raise HTTPException(status_code=400, detail="owner_user_id not found.")
    exp = _parse_iso_dt(body.expires_at.strip())
    allowed = normalize_allowed_study_ids(body.allowed_study_ids)
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail="allowed_study_ids must contain at least one valid study id.",
        )
    rec, plain = store.create_mcp_api_key(
        body.name.strip(),
        body.scopes,
        body.owner_user_id.strip(),
        expires_at=exp,
        allowed_study_ids=allowed,
    )
    return {
        "key": {
            "id": rec.id,
            "name": rec.name,
            "keyPrefix": rec.key_prefix,
            "scopes": rec.scopes,
            "allowedStudyIds": rec.allowed_study_ids,
            "ownerUserId": rec.owner_user_id,
            "createdAt": rec.created_at.isoformat(),
            "expiresAt": rec.expires_at.isoformat() if rec.expires_at else None,
        },
        "secret": plain,
    }


@router.patch("/admin/mcp-api-keys/{key_id}")
def patch_mcp_api_key_route(
    key_id: str,
    body: PatchMcpApiKeyBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    _require_superuser(store, user)
    keys = [k for k in store.list_mcp_api_keys() if k.id == key_id]
    if not keys:
        raise HTTPException(status_code=404, detail="API key not found.")
    if body.name is not None and not str(body.name).strip():
        raise HTTPException(status_code=400, detail="name cannot be empty.")
    if body.clear_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Removing expiry is not allowed. Set expires_at to a new ISO-8601 datetime instead.",
        )
    exp = (
        _parse_iso_dt(body.expires_at.strip())
        if body.expires_at and str(body.expires_at).strip()
        else None
    )
    if body.clear_allowed_study_ids:
        raise HTTPException(
            status_code=400,
            detail="Study scope cannot be cleared; at least one study is required.",
        )
    owner_kw: dict = {}
    if body.owner_user_id is not None:
        ou = body.owner_user_id.strip()
        if not ou:
            raise HTTPException(status_code=400, detail="owner_user_id cannot be empty.")
        if not store.get_user_by_id(ou):
            raise HTTPException(status_code=400, detail="owner_user_id not found.")
        owner_kw["owner_user_id"] = ou
    if body.allowed_study_ids is not None:
        norm_studies = normalize_allowed_study_ids(body.allowed_study_ids)
        if not norm_studies:
            raise HTTPException(
                status_code=400,
                detail="allowed_study_ids must contain at least one valid study id.",
            )
        store.update_mcp_api_key(
            key_id,
            name=str(body.name).strip() if body.name is not None else None,
            expires_at=exp,
            clear_expires_at=False,
            allowed_study_ids=norm_studies,
            **owner_kw,
        )
    else:
        store.update_mcp_api_key(
            key_id,
            name=str(body.name).strip() if body.name is not None else None,
            expires_at=exp,
            clear_expires_at=False,
            **owner_kw,
        )
    updated = [k for k in store.list_mcp_api_keys() if k.id == key_id][0]
    return {
        "key": {
            "id": updated.id,
            "name": updated.name,
            "keyPrefix": updated.key_prefix,
            "scopes": updated.scopes,
            "allowedStudyIds": updated.allowed_study_ids,
            "ownerUserId": updated.owner_user_id,
            "createdAt": updated.created_at.isoformat(),
            "revokedAt": updated.revoked_at.isoformat() if updated.revoked_at else None,
            "lastUsedAt": updated.last_used_at.isoformat() if updated.last_used_at else None,
            "expiresAt": updated.expires_at.isoformat() if updated.expires_at else None,
        }
    }


@router.post("/admin/mcp-api-keys/{key_id}/rotate")
def rotate_mcp_api_key_route(
    key_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Revoke the key and return a new secret (shown once)."""
    _require_superuser(store, user)
    try:
        rec, plain = store.rotate_mcp_api_key(key_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "key": {
            "id": rec.id,
            "name": rec.name,
            "keyPrefix": rec.key_prefix,
            "scopes": rec.scopes,
            "allowedStudyIds": rec.allowed_study_ids,
            "ownerUserId": rec.owner_user_id,
            "createdAt": rec.created_at.isoformat(),
            "expiresAt": rec.expires_at.isoformat() if rec.expires_at else None,
        },
        "secret": plain,
    }


@router.post("/admin/mcp-api-keys/{key_id}/revoke")
def revoke_mcp_api_key_route(
    key_id: str,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    _require_superuser(store, user)
    before = [k for k in store.list_mcp_api_keys() if k.id == key_id]
    if not before:
        raise HTTPException(status_code=404, detail="API key not found.")
    store.revoke_mcp_api_key(key_id)
    return {"ok": True}


@router.post("/admin/tool-invocations/purge")
def purge_tool_invocation_logs(
    body: PurgeInvocationLogsBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Delete audit rows older than the cutoff (superuser)."""
    _require_superuser(store, user)
    cutoff = datetime.now(timezone.utc) - timedelta(days=body.older_than_days)
    removed = store.purge_tool_invocation_logs_before(cutoff)
    return {"ok": True, "removed": removed, "cutoff": cutoff.isoformat()}


@router.get("/admin/tool-invocations")
def list_tool_invocations(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    from_: Optional[str] = Query(default=None, alias="from"),
    to_: Optional[str] = Query(default=None, alias="to"),
    api_key_id: Optional[str] = None,
    tool: Optional[str] = None,
    study_id: Optional[str] = None,
    status_min: Optional[int] = Query(default=None),
    status_max: Optional[int] = Query(default=None),
):
    _require_superuser(store, user)
    if status_min is not None and (status_min < 100 or status_min > 599):
        raise HTTPException(status_code=400, detail="status_min must be between 100 and 599.")
    if status_max is not None and (status_max < 100 or status_max > 599):
        raise HTTPException(status_code=400, detail="status_max must be between 100 and 599.")
    from_ts = _parse_iso_dt(from_)
    to_ts = _parse_iso_dt(to_)
    rows, total = store.list_tool_invocation_logs(
        limit=limit,
        offset=offset,
        from_ts=from_ts,
        to_ts=to_ts,
        api_key_id=api_key_id,
        tool_name=tool,
        study_id=study_id or None,
        status_min=status_min,
        status_max=status_max,
    )
    return {
        "total": total,
        "invocations": [
            {
                "id": r.id,
                "createdAt": r.created_at.isoformat(),
                "apiKeyId": r.api_key_id,
                "keySource": r.key_source,
                "keyPrefix": r.key_prefix,
                "toolName": r.tool_name,
                "studyId": r.study_id,
                "statusCode": r.status_code,
                "durationMs": r.duration_ms,
                "errorDetail": r.error_detail,
            }
            for r in rows
        ],
    }
