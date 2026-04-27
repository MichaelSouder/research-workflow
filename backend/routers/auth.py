"""
Google OAuth login, callback, logout, and current user.
Sessions stored in datastore; session id in cookie.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from backend.datastore.base import Datastore, User, STUDY_ROLE_ADMIN, STUDY_ROLE_EDITOR
from backend.passwords import PENDING_GOOGLE_PREFIX, verify_password

# OAuth: authlib Starlette integration
OAUTH = None

SESSION_COOKIE_NAME = "session_id"
SESSION_SECRET_ENV = "SESSION_SECRET"
FRONTEND_URL_ENV = "FRONTEND_URL"
# Optional override; if unset, redirect URI is {FRONTEND_URL}/auth/callback (required for Vite proxy dev).
OAUTH_REDIRECT_URI_ENV = "OAUTH_REDIRECT_URI"
GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
SESSION_TTL_DAYS = 7
BYPASS_AUTH_DEV_ENV = "BYPASS_AUTH_DEV"
SUPERUSER_EMAILS_ENV = "SUPERUSER_EMAILS"
DEV_USER_GOOGLE_ID = "dev-bypass-local"
DEV_USER_EMAIL = "dev@local"
DEV_USER_NAME = "Dev User"

# Project root for reading .env on disk (debug only).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"


def _google_client_id_fingerprint(cid: str) -> str | None:
    """Short, human-checkable fingerprint (avoids only showing …googleusercontent.com)."""
    if not (cid or "").strip():
        return None
    cid = cid.strip()
    base = cid.split(".apps.googleusercontent.com", 1)[0] if ".apps.googleusercontent.com" in cid else cid
    if len(base) <= 28:
        return base
    return f"{base[:14]}…{base[-14:]}"


def _dotenv_file_value(key: str) -> str | None:
    """Best-effort parse of KEY=value from .env (no interpolation). For diagnostics."""
    if not _DOTENV_PATH.is_file():
        return None
    prefix = f"{key}="
    try:
        text = _DOTENV_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith(prefix):
            raw = s[len(prefix) :].strip()
            if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                raw = raw[1:-1]
            return raw.strip()
    return None


def _bypass_auth_dev_enabled() -> bool:
    """
    True when bypass is allowed (development only).
    Either BYPASS_AUTH_DEV=1, or Google OAuth not configured (no GOOGLE_CLIENT_ID).
    """
    v = (os.environ.get(BYPASS_AUTH_DEV_ENV) or "").strip().lower().strip('"').strip("'")
    if v in ("1", "true", "yes", "on"):
        return True
    # If Google OAuth isn't set up, allow bypass so dev works without .env
    if not (os.environ.get(GOOGLE_CLIENT_ID_ENV) or "").strip():
        return True
    return False


def _frontend_base_for_request(request: Request) -> str:
    """
    Base URL for redirects after login/logout. For loopback dev, use the browser Host header
    so http://127.0.0.1:48722 and http://localhost:48722 stay consistent with Starlette's OAuth
    session cookie (cookie host must match the host that starts /auth/login).

    When FRONTEND_URL's port differs from the Vite port (e.g. .env says :48722 but you run on :15421),
    we still follow the request Host. Otherwise the session cookie is set for the origin that served
    /auth/dev-login while the redirect would send the browser to another origin — /auth/me then 401s.
    """
    fe = (os.environ.get(FRONTEND_URL_ENV) or "http://localhost:48722").strip().rstrip("/")
    parsed = urlparse(fe if "://" in fe else f"http://{fe}")
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        return fe

    raw = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if not raw:
        return fe

    try:
        if ":" in raw:
            host_part, port_str = raw.rsplit(":", 1)
            int(port_str)  # validate numeric port
        else:
            host_part = raw
    except ValueError:
        return fe

    if host_part.lower() in ("localhost", "127.0.0.1"):
        scheme = parsed.scheme or "http"
        return f"{scheme}://{raw}".rstrip("/")

    return fe


def _get_oauth():
    global OAUTH
    if OAUTH is not None:
        return OAUTH
    from authlib.integrations.starlette_client import OAuth

    client_id = (os.environ.get(GOOGLE_CLIENT_ID_ENV) or "").strip()
    client_secret = (os.environ.get(GOOGLE_CLIENT_SECRET_ENV) or "").strip()
    if not client_id or not client_secret:
        return None
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs={"scope": "openid email profile"},
    )
    OAUTH = oauth
    return oauth


def _oauth_redirect_uri(request: Request) -> str:
    """
    OAuth redirect_uri sent to Google must exactly match a URI in Google Cloud Console.
    Uses FRONTEND_URL (or OAUTH_REDIRECT_URI) but, for loopback, aligns with the request Host
    so the Starlette session cookie for OAuth state matches the callback URL (localhost vs 127.0.0.1).
    """
    explicit = (os.environ.get(OAUTH_REDIRECT_URI_ENV) or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = _frontend_base_for_request(request)
    return f"{base}/auth/callback"


def describe_oauth_redirect_uri() -> str:
    """Used for startup logging (no Request); actual /auth/login uses Host on loopback when applicable."""
    explicit = (os.environ.get(OAUTH_REDIRECT_URI_ENV) or "").strip()
    if explicit:
        return explicit.rstrip("/")
    fe = (os.environ.get(FRONTEND_URL_ENV) or "http://localhost:48722").strip().rstrip("/")
    return (
        f"{fe}/auth/callback "
        f"(on loopback dev, Host header can switch localhost ↔ 127.0.0.1 — register both redirect URIs in Google Cloud)"
    )


def get_datastore(request: Request) -> Datastore:
    """Get datastore from app state (set in lifespan)."""
    store = getattr(request.app.state, "datastore", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Datastore not configured")
    return store


def _apply_superuser_policy(store: Datastore, user: User) -> User:
    """Set platform superuser from SUPERUSER_EMAILS, dev@local, or dev bypass."""
    u = user
    if _bypass_auth_dev_enabled() and user.google_id == DEV_USER_GOOGLE_ID:
        if not user.is_superuser:
            store.set_user_superuser(user.id, True)
            u = store.get_user_by_id(user.id) or user
        return u
    emails_raw = (os.environ.get(SUPERUSER_EMAILS_ENV) or "").strip()
    allowed = {e.strip().lower() for e in emails_raw.split(",") if e.strip()}
    allowed.add(DEV_USER_EMAIL.lower())
    if user.email.lower() in allowed and not user.is_superuser:
        store.set_user_superuser(user.id, True)
        u = store.get_user_by_id(user.id) or user
    return u


def _ensure_user_has_study(store: Datastore, user: User) -> None:
    """If user has no studies but a study exists (e.g. Default), assign them as editor."""
    if store.list_studies_for_user(user.id):
        return
    any_study = store.get_any_study()
    if any_study:
        store.set_user_study_role(user.id, any_study.id, STUDY_ROLE_EDITOR)


async def get_current_user(
    request: Request,
    store: Annotated[Datastore, Depends(get_datastore)],
) -> User:
    """Dependency: return current user from session cookie or raise 401."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    user = store.get_user_by_id(session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


router = APIRouter(prefix="/auth", tags=["auth"])


class PasswordLoginBody(BaseModel):
    email: str = Field(default="", max_length=320)
    password: str = Field(default="", max_length=1024)


@router.post("/password-login")
async def password_login(request: Request, body: PasswordLoginBody):
    """Email + password session (users with a stored password hash, e.g. platform-provisioned)."""
    email = (body.email or "").strip()
    pwd = body.password or ""
    if not email or not pwd:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    store = get_datastore(request)
    target = store.get_user_by_email(email)
    if not target or not target.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(pwd, target.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user = _apply_superuser_policy(store, target)
    _ensure_user_has_study(store, user)
    session_id = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    store.create_session(user_id=user.id, session_id=session_id, expires_at=expires)
    frontend_url = _frontend_base_for_request(request)
    response = JSONResponse({"ok": True, "redirect": f"{frontend_url}/"})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("HTTPS") == "1",
    )
    return response


@router.get("/dev-bypass-status")
async def dev_bypass_status():
    """Tell the login page whether GET /auth/dev-login will succeed (requires BYPASS_AUTH_DEV=1 when Google OAuth is configured)."""
    return {"bypassAvailable": _bypass_auth_dev_enabled()}


@router.get("/dev-login")
async def dev_login(request: Request):
    """
    Development-only: create a fake session and redirect to dashboard.
    Only available when BYPASS_AUTH_DEV=1 (or true). Do not set in production.
    """
    if not _bypass_auth_dev_enabled():
        return HTMLResponse(
            status_code=403,
            content=(
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\"/><title>Bypass disabled</title></head>"
                "<body style=\"font-family:system-ui;max-width:36rem;margin:2rem;line-height:1.5\">"
                "<h1>Dev bypass is off</h1>"
                "<p>When <code>GOOGLE_CLIENT_ID</code> is set, enable bypass by adding "
                "<strong><code>BYPASS_AUTH_DEV=1</code></strong> to the project <code>.env</code> file, "
                "then restart the backend.</p>"
                "<p><a href=\"/login\">Back to login</a></p></body></html>"
            ),
        )
    store = get_datastore(request)
    user = store.create_or_update_user(
        google_id=DEV_USER_GOOGLE_ID,
        email=DEV_USER_EMAIL,
        name=DEV_USER_NAME,
    )
    user = _apply_superuser_policy(store, user)
    _ensure_user_has_study(store, user)
    # Dev user is always admin for every study they have access to
    for study, _ in store.list_studies_for_user(user.id):
        store.set_user_study_role(user.id, study.id, STUDY_ROLE_ADMIN)
    session_id = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    store.create_session(user_id=user.id, session_id=session_id, expires_at=expires)
    frontend_url = _frontend_base_for_request(request)
    redirect = RedirectResponse(url=f"{frontend_url}/", status_code=302)
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("HTTPS") == "1",
    )
    return redirect


@router.get("/debug/oauth-redirect")
async def debug_oauth_redirect(request: Request):
    """
    Show the exact redirect_uri and client id this server uses. Use to fix redirect_uri_mismatch:
    the redirect URI must be listed on **the same** OAuth 2.0 Client ID as GOOGLE_CLIENT_ID in .env.
    """
    cid = (os.environ.get(GOOGLE_CLIENT_ID_ENV) or "").strip()
    file_cid = _dotenv_file_value(GOOGLE_CLIENT_ID_ENV)
    file_cid_n = file_cid.strip() if file_cid else ""
    mismatch = bool(file_cid_n and cid and file_cid_n != cid)
    warnings = []
    if mismatch:
        warnings.append(
            "GOOGLE_CLIENT_ID in the running process does not match `.env` on disk. "
            "Restart the backend after saving `.env`, and run `unset GOOGLE_CLIENT_ID` (and FRONTEND_URL) "
            "in the terminal if they were exported in your shell."
        )
    resolved = _oauth_redirect_uri(request)
    return {
        "redirect_uri": resolved,
        "redirect_uri_length": len(resolved),
        "google_client_id": cid or None,
        "google_client_id_fingerprint": _google_client_id_fingerprint(cid),
        "frontend_url": (os.environ.get(FRONTEND_URL_ENV) or "").strip() or None,
        "oauth_redirect_uri_override": (os.environ.get(OAUTH_REDIRECT_URI_ENV) or "").strip() or None,
        "dotenv_file_google_client_id_matches_process": (not mismatch) if file_cid else None,
        "warnings": warnings,
        "checklist": [
            "Project `.env` is loaded with override=True so it wins over shell exports — restart the backend after editing `.env`.",
            "In Google Cloud → APIs & Services → Credentials, open the OAuth 2.0 Client ID whose **Client ID** matches google_client_id above (not a different client).",
            "Under that client, Authorized redirect URIs must include redirect_uri exactly (character-for-character). Add both http://localhost:48722/auth/callback and http://127.0.0.1:48722/auth/callback if you switch hosts.",
            "Authorized JavaScript origins must include the same origin you use in the browser (e.g. http://localhost:48722).",
            "Credential type must be **Web application** (not Desktop / iOS / Android).",
        ],
    }


@router.get("/login")
async def login(request: Request):
    """Redirect to Google OAuth."""
    oauth = _get_oauth()
    if not oauth:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    redirect_uri = _oauth_redirect_uri(request)
    return await oauth.google.authorize_redirect(request, redirect_uri)


def _oauth_callback_error_page(title: str, body: str, status: int = 400) -> HTMLResponse:
    """Browser-friendly error (callback is a top-level navigation)."""
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return HTMLResponse(
        status_code=status,
        content=(
            f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"/><title>{title}</title></head>"
            f"<body style=\"font-family:system-ui;max-width:42rem;margin:2rem;line-height:1.5\">"
            f"<h1>{title}</h1><pre style=\"white-space:pre-wrap;background:#f4f4f5;padding:1rem;border-radius:8px\">{safe}</pre>"
            f"<p><a href=\"/login\">Back to login</a></p></body></html>"
        ),
    )


@router.get("/callback", name="auth_callback")
async def auth_callback(request: Request, response: Response):
    """Handle Google OAuth callback; create session and redirect to frontend."""
    oauth = _get_oauth()
    if not oauth:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    q = request.query_params
    if q.get("error"):
        # Google redirects here with error= when consent denied, misconfiguration, etc.
        desc = (q.get("error_description") or "").replace("+", " ")
        err = q.get("error", "")
        detail = f"{err}: {desc}".strip()
        hint = (
            "If this is redirect_uri_mismatch: open /auth/debug/oauth-redirect and register that exact redirect_uri "
            "under Authorized redirect URIs, and add your dev origin (e.g. http://localhost:48722) under "
            "Authorized JavaScript origins. Wait a few minutes after saving."
        )
        return _oauth_callback_error_page(
            "Google sign-in error",
            detail + ("\n\n" + hint if "redirect_uri" in err.lower() or "invalid" in err.lower() else ""),
            status=400,
        )

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        msg = str(e)
        hint = (
            "If this mentions state: use the same host you started from (localhost vs 127.0.0.1), "
            "clear site cookies for that host, restart the backend, and try again. "
            "Both http://localhost:48722/auth/callback and http://127.0.0.1:48722/auth/callback "
            "must be registered as redirect URIs if you switch hosts."
        )
        return _oauth_callback_error_page("OAuth token exchange failed", f"{msg}\n\n{hint}", status=400)
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(status_code=400, detail="No user info from Google")
    google_id = userinfo.get("sub") or userinfo.get("id")
    email = userinfo.get("email") or ""
    name = userinfo.get("name") or userinfo.get("email") or "User"
    if not google_id:
        raise HTTPException(status_code=400, detail="No Google id in user info")

    store = get_datastore(request)
    by_google = store.get_user_by_google_id(google_id)
    if by_google:
        user = store.create_or_update_user(google_id=google_id, email=email, name=name)
    else:
        pending = store.get_user_by_email(email)
        if pending and (pending.google_id or "").startswith(PENDING_GOOGLE_PREFIX):
            user = store.link_oauth_to_pending_user(pending.id, google_id, email, name)
        else:
            user = store.create_or_update_user(google_id=google_id, email=email, name=name)
    user = _apply_superuser_policy(store, user)
    _ensure_user_has_study(store, user)
    session_id = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    store.create_session(user_id=user.id, session_id=session_id, expires_at=expires)

    frontend_url = _frontend_base_for_request(request)
    redirect = RedirectResponse(url=f"{frontend_url}/", status_code=302)
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_TTL_DAYS * 24 * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=os.environ.get("HTTPS") == "1",
    )
    return redirect


@router.post("/logout")
@router.get("/logout")
async def logout(request: Request, response: Response):
    """Clear session and cookie; return redirect to login."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        store = get_datastore(request)
        store.delete_session(session_id)
    frontend_url = _frontend_base_for_request(request)
    redirect = RedirectResponse(url=f"{frontend_url}/login", status_code=302)
    redirect.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return redirect


@router.get("/me")
async def auth_me(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Return current user for frontend (avatar, email, platform superuser flag)."""
    u = store.get_user_by_id(user.id) or user
    u = _apply_superuser_policy(store, u)
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "isSuperuser": u.is_superuser,
    }
