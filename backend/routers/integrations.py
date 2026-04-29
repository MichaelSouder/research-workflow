"""Integration downloads and context for MCP / ChatGPT (session-authenticated)."""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.datastore.base import Datastore, User
from backend.routers import tool_api as tool_api_mod
from backend.routers.auth import get_current_user
from backend.routers.studies import get_datastore

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "integrations_bundle"


@router.get("/ping")
def integrations_ping() -> dict:
    """No auth. Use in a browser or curl to confirm the running backend serves integration routes."""
    return {"ok": True, "integrations": True}


def _public_tool_api_base() -> str:
    explicit = (os.environ.get("TOOL_API_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    fe = (os.environ.get("FRONTEND_URL") or "").strip().rstrip("/")
    if fe:
        return fe
    return "http://127.0.0.1:48721"


def _mcp_key_active(k) -> bool:
    if k.revoked_at:
        return False
    exp = k.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= exp:
            return False
    return True


def _mcp_key_inactive_reason(k) -> str | None:
    """If the key is not usable for Integrations / invoke, return why; otherwise None."""
    if k.revoked_at:
        return "revoked"
    exp = k.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= exp:
            return "expired"
    return None


def _owner_matches_session(user_id: str, owner_user_id: str | None) -> bool:
    """True when the key is owned by the signed-in user (normalize DB / client id quirks)."""
    a = str(user_id or "").strip().lower()
    b = str(owner_user_id or "").strip().lower()
    return bool(a) and a == b


@router.get("/context")
def get_integration_context(user: Annotated[User, Depends(get_current_user)]):
    base = _public_tool_api_base()
    return {
        "publicToolApiBase": base,
        "openapiUrl": f"{base}/v1/openapi.json",
        "invokeUrl": f"{base}/v1/tools/invoke",
    }


@router.get("/mcp-api-keys")
def list_my_mcp_api_keys(
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """Tool API keys owned by the current user (metadata only; no secrets)."""
    out = []
    owned_inactive: list[dict] = []
    for k in store.list_mcp_api_keys():
        if not _owner_matches_session(user.id, k.owner_user_id):
            continue
        if _mcp_key_active(k):
            out.append(
                {
                    "id": k.id,
                    "name": k.name,
                    "keyPrefix": k.key_prefix,
                    "scopes": k.scopes,
                    "allowedStudyIds": k.allowed_study_ids,
                    "createdAt": k.created_at.isoformat(),
                    "expiresAt": k.expires_at.isoformat() if k.expires_at else None,
                }
            )
            continue
        reason = _mcp_key_inactive_reason(k) or "inactive"
        owned_inactive.append(
            {
                "id": k.id,
                "name": k.name,
                "keyPrefix": k.key_prefix,
                "reason": reason,
                "expiresAt": k.expires_at.isoformat() if k.expires_at else None,
                "revokedAt": k.revoked_at.isoformat() if k.revoked_at else None,
            }
        )
        if len(owned_inactive) >= 25:
            break
    body: dict = {"keys": out, "viewerUserId": user.id, "ownedButInactive": owned_inactive}
    # Superusers: explain "0 keys" when keys exist but Owner ≠ session (common with duplicate dev@local users).
    if user.is_superuser:
        other = []
        for k in store.list_mcp_api_keys():
            if not _mcp_key_active(k):
                continue
            if _owner_matches_session(user.id, k.owner_user_id):
                continue
            other.append(
                {
                    "id": k.id,
                    "name": k.name,
                    "keyPrefix": k.key_prefix,
                    "ownerUserId": k.owner_user_id,
                }
            )
            if len(other) >= 30:
                break
        body["activeKeysNotOwnedByYou"] = other
        inactive_other: list[dict] = []
        for k in store.list_mcp_api_keys():
            if _mcp_key_active(k):
                continue
            if _owner_matches_session(user.id, k.owner_user_id):
                continue
            inactive_other.append(
                {
                    "id": k.id,
                    "name": k.name,
                    "keyPrefix": k.key_prefix,
                    "ownerUserId": k.owner_user_id,
                    "reason": _mcp_key_inactive_reason(k) or "inactive",
                }
            )
            if len(inactive_other) >= 30:
                break
        body["inactiveKeysNotOwnedByYou"] = inactive_other
    return body


class ClaudeBundleBody(BaseModel):
    api_key_id: str = Field(..., min_length=1, max_length=64)
    api_key_secret: str = Field(..., min_length=8, max_length=512)


@router.post("/bundles/claude")
def download_claude_bundle(
    body: ClaudeBundleBody,
    user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Datastore, Depends(get_datastore)],
):
    """
    Build a zip with bridge script, requirements, README, and Claude Desktop config
    embedding the provided API key (verified once against the stored hash).
    """
    token = body.api_key_secret.strip()
    resolved = store.resolve_mcp_api_key_secret(token)
    if not resolved:
        raise HTTPException(status_code=403, detail="Invalid API key secret.")
    key_id, _scopes, _prefix, _allowed, owner_id = resolved
    if key_id != body.api_key_id.strip():
        raise HTTPException(status_code=403, detail="Secret does not match the selected key id.")
    if not _owner_matches_session(user.id, owner_id):
        raise HTTPException(status_code=403, detail="You can only download a bundle for your own API keys.")
    tool_api_mod._register_tools()
    tool_names = sorted(tool_api_mod._TOOL_MAP.keys())
    names_json = json.dumps(tool_names)
    base = _public_tool_api_base()

    bridge_src = (_BUNDLE_DIR / "bridge_stdio.py").read_text(encoding="utf-8")
    launcher_src = (_BUNDLE_DIR / "launcher.py").read_text(encoding="utf-8")
    install_src = (_BUNDLE_DIR / "install_bundle.py").read_text(encoding="utf-8")
    readme = f"""# Research Workflow — Claude Desktop (MCP bridge)

Small MCP server that forwards tool calls to your deployment’s HTTP tool API (`{base}`).

## Quick install (macOS / Linux)

1. **Unzip** this folder to a stable path you keep (not a transient Downloads-only copy), e.g.  
   `~/research-workflow-claude-mcp`
2. **Install Python deps** (use a venv if you like):

   ```bash
   cd research-workflow-claude
   python3 -m pip install -r requirements-bridge.txt
   ```

3. **Generate the Claude config snippet** (fills in absolute paths — avoids “file not found” when Claude starts MCP with the wrong working directory):

   ```bash
   python3 install_bundle.py
   ```

4. Open **`claude_desktop_config.fragment.json`** (created in this folder). Copy the **`mcpServers`** object into Claude Desktop → Settings → Developer → Edit config, or merge into:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
5. If **`python3`** is not the interpreter where you installed deps, edit **`command`** in the fragment to the full path (run `which python3`).
6. **Restart Claude Desktop.**

## URLs

- Tool API base: `{base}`
- OpenAPI: `{base}/v1/openapi.json`

## Security

The API key in `claude_desktop_config.fragment.template.json` / generated fragment is sensitive. Do not commit this folder to git or share it.

Sensitive tool responses are masked **on the server** according to your account’s “Tool API data proxy” setting (Platform admin can change it).
"""

    req_txt = "mcp>=1.0\nhttpx>=0.28.0\n"

    env_block = {
        "RW_BASE_URL": base,
        "RW_API_KEY": token,
        "RW_TOOL_NAMES_JSON": names_json,
    }
    # Placeholder replaced by install_bundle.py so cwd/args use this folder’s absolute path.
    _bundle_placeholder = "__BUNDLE_DIR__"
    fragment_template = {
        "mcpServers": {
            "research-workflow": {
                "command": "python3",
                "args": ["-u", f"{_bundle_placeholder}/launcher.py"],
                "cwd": _bundle_placeholder,
                "env": env_block,
            }
        }
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("research-workflow-claude/README.md", readme)
        zf.writestr("research-workflow-claude/requirements-bridge.txt", req_txt)
        zf.writestr("research-workflow-claude/bridge_stdio.py", bridge_src)
        zf.writestr("research-workflow-claude/launcher.py", launcher_src)
        zf.writestr("research-workflow-claude/install_bundle.py", install_src)
        zf.writestr(
            "research-workflow-claude/claude_desktop_config.fragment.template.json",
            json.dumps(fragment_template, indent=2),
        )
    buf.seek(0)
    filename = "research-workflow-claude-mcp-bundle.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
