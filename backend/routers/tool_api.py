"""
HTTP tool API for ChatGPT/Gemini: POST /v1/tools/invoke with API key auth.
Serves OpenAPI spec at GET /v1/openapi.json.

Auth: (1) MCP_API_KEY / MCP_API_KEYS env keys, or (2) datastore MCP API keys (Platform admin).
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ai.proxy import invoke_and_mock
from ai.proxy.defaults import SENSITIVE_TOOLS
from ai.proxy_env import data_proxy_request_context, env_key_data_proxy_default
from backend.datastore.base import Datastore, User

logger = logging.getLogger(__name__)

MCP_API_KEY_ENV = "MCP_API_KEY"
MCP_API_KEYS_ENV = "MCP_API_KEYS"


def _get_env_api_keys() -> set[str]:
    single = os.environ.get(MCP_API_KEY_ENV, "").strip()
    multiple = os.environ.get(MCP_API_KEYS_ENV, "").strip()
    keys = set()
    if single:
        keys.add(single)
    for k in multiple.split(","):
        k = k.strip()
        if k:
            keys.add(k)
    return keys


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-API-Key") or "").strip()


@dataclass
class McpToolAuth:
    store: Datastore
    user: User
    api_key_id: Optional[str]
    """Scopes from DB key; empty list = all tools. Ignored when from_env is True."""
    scopes: list[str]
    """Study allowlist from DB key; empty = all studies when study_id appears in tool arguments."""
    allowed_study_ids: list[str]
    from_env: bool
    key_source: str  # "env" | "database"
    key_prefix_display: str
    """When True, sensitive tools use server-side data proxy (same behavior as MCP_DATA_PROXY_ENABLED)."""
    data_proxy_enabled: bool


def _append_auth_failure_log(store: Datastore, status_code: int, detail: str) -> None:
    """Record failed tool API auth (missing/invalid key or misconfiguration)."""
    try:
        store.append_tool_invocation_log(
            api_key_id=None,
            key_source="auth",
            key_prefix_display="—",
            tool_name="",
            study_id=None,
            status_code=status_code,
            duration_ms=0,
            error_detail=(detail or "")[:500],
        )
    except Exception as e:
        logger.warning("tool auth failure log failed: %s", e)


def authenticate_mcp_tool_request(request: Request) -> McpToolAuth:
    """Validate API key (env or datastore) and return context. Sets ai context."""
    token = _extract_bearer(request)
    store = getattr(request.app.state, "datastore", None)
    if not store:
        raise HTTPException(status_code=503, detail="Datastore not configured.")

    from ai.auth import get_mcp_user
    from ai.context import set_context

    env_keys = _get_env_api_keys()
    user = get_mcp_user(store)

    if token and env_keys and token in env_keys:
        set_context(store, user)
        return McpToolAuth(
            store=store,
            user=user,
            api_key_id=None,
            scopes=[],
            allowed_study_ids=[],
            from_env=True,
            key_source="env",
            key_prefix_display="env",
            data_proxy_enabled=env_key_data_proxy_default(),
        )

    resolved = store.resolve_mcp_api_key_secret(token) if token else None
    if resolved:
        key_id, scopes, prefix, allowed_study_ids, owner_user_id = resolved
        if not (owner_user_id and str(owner_user_id).strip()):
            d = "API key has no owner. Replace it with a new key that assigns an owner."
            _append_auth_failure_log(store, 403, d)
            raise HTTPException(status_code=403, detail=d)
        if not allowed_study_ids:
            d = "API key is not study-scoped. Replace it with a new key that allows at least one study."
            _append_auth_failure_log(store, 403, d)
            raise HTTPException(status_code=403, detail=d)
        store.touch_mcp_api_key_last_used(key_id)
        owner = store.get_user_by_id(owner_user_id)
        proxy_on = owner.tool_api_data_proxy_enabled if owner else True
        set_context(store, user)
        return McpToolAuth(
            store=store,
            user=user,
            api_key_id=key_id,
            scopes=list(scopes),
            allowed_study_ids=list(allowed_study_ids),
            from_env=False,
            key_source="database",
            key_prefix_display=prefix or (key_id[:8] + "…"),
            data_proxy_enabled=proxy_on,
        )

    if not env_keys and not store.has_active_mcp_api_keys():
        detail = (
            "Tool API not configured: set MCP_API_KEY or MCP_API_KEYS, or create an API key in Platform admin."
        )
        _append_auth_failure_log(store, 503, detail)
        raise HTTPException(status_code=503, detail=detail)

    d401 = "Invalid or missing API key."
    _append_auth_failure_log(store, 401, d401)
    raise HTTPException(status_code=401, detail=d401)


def _tool_allowed(auth: McpToolAuth, tool_name: str) -> bool:
    if auth.from_env:
        return True
    if not auth.scopes:
        return True
    return tool_name in auth.scopes


def _arguments_for_tool_fn(fn: Callable[..., Any], arguments: dict) -> dict:
    """Drop keys the tool implementation does not accept (e.g. study_id for qual_studies_list)."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return dict(arguments)
    names = set(sig.parameters.keys())
    return {k: v for k, v in arguments.items() if k in names}


def _study_allowed(auth: McpToolAuth, study_id: Optional[str]) -> bool:
    """Database keys are always study-scoped: every invoke must include a study_id in arguments."""
    if auth.from_env:
        return True
    if not auth.allowed_study_ids:
        return False
    sid = (study_id or "").strip()
    if not sid:
        return False
    return sid in auth.allowed_study_ids


def _append_invocation_log(
    store: Datastore,
    *,
    auth: McpToolAuth,
    tool_name: str,
    study_id: Optional[str],
    status_code: int,
    duration_ms: int,
    error_detail: Optional[str] = None,
) -> None:
    try:
        store.append_tool_invocation_log(
            api_key_id=auth.api_key_id,
            key_source=auth.key_source,
            key_prefix_display=auth.key_prefix_display,
            tool_name=tool_name,
            study_id=study_id,
            status_code=status_code,
            duration_ms=duration_ms,
            error_detail=error_detail,
        )
    except Exception as e:
        logger.warning("tool_invocation_log failed: %s", e)


# Backwards-compatible name for tests / imports
def get_tool_api_user(request: Request) -> tuple[Datastore, User]:
    """Validate API key and return (store, mcp_user)."""
    ctx = authenticate_mcp_tool_request(request)
    return ctx.store, ctx.user


router = APIRouter(prefix="/v1", tags=["tools"])

_TOOL_MAP: dict[str, tuple[Any, str]] = {}


def _register_tools():
    from ai.tools import box_grid, components, config, distribution, pipelines, run, status, studies

    for name, mod, fn in [
        ("qual_studies_list", studies, "qual_studies_list"),
        ("qual_study_get", studies, "qual_study_get"),
        ("qual_study_users_list", studies, "qual_study_users_list"),
        ("qual_study_create", studies, "qual_study_create"),
        ("qual_study_update", studies, "qual_study_update"),
        ("qual_study_delete", studies, "qual_study_delete"),
        ("qual_study_users_set", studies, "qual_study_users_set"),
        ("qual_study_user_add", studies, "qual_study_user_add"),
        ("qual_pipelines_list", pipelines, "qual_pipelines_list"),
        ("qual_pipeline_get", pipelines, "qual_pipeline_get"),
        ("qual_pipeline_create", pipelines, "qual_pipeline_create"),
        ("qual_pipeline_update", pipelines, "qual_pipeline_update"),
        ("qual_pipeline_delete", pipelines, "qual_pipeline_delete"),
        ("qual_study_config_get", config, "qual_study_config_get"),
        ("qual_config_get", config, "qual_config_get"),
        ("qual_study_config_set", config, "qual_study_config_set"),
        ("qual_config_set", config, "qual_config_set"),
        ("qual_status", status, "qual_status"),
        ("qual_study_status", status, "qual_study_status"),
        ("qual_activity", status, "qual_activity"),
        ("qual_study_activity", status, "qual_study_activity"),
        ("qual_study_errors", status, "qual_study_errors"),
        ("qual_run_start", run, "qual_run_start"),
        ("qual_run_stop", run, "qual_run_stop"),
        ("qual_distribution_contacts", distribution, "qual_distribution_contacts"),
        ("qual_distribution_check", distribution, "qual_distribution_check"),
        ("qual_distribution_status", distribution, "qual_distribution_status"),
        ("qual_distribution_list", distribution, "qual_distribution_list"),
        ("qual_distribution_send_preview", distribution, "qual_distribution_send_preview"),
        ("qual_distribution_export", distribution, "qual_distribution_export"),
        ("qual_distribution_send", distribution, "qual_distribution_send"),
        ("qual_distribution_delete_unsent", distribution, "qual_distribution_delete_unsent"),
        ("qual_distribution_contact_patch", distribution, "qual_distribution_contact_patch"),
        ("qual_box_folders", box_grid, "qual_box_folders"),
        ("qual_study_box_config_status", box_grid, "qual_study_box_config_status"),
        ("qual_grid_studies", box_grid, "qual_grid_studies"),
        ("qual_box_config_set", box_grid, "qual_box_config_set"),
        ("qual_components_list", components, "qual_components_list"),
        ("qual_component_get", components, "qual_component_get"),
        ("qual_component_run_debug", components, "qual_component_run_debug"),
        ("qual_component_create", components, "qual_component_create"),
        ("qual_component_update", components, "qual_component_update"),
        ("qual_component_delete", components, "qual_component_delete"),
    ]:
        _TOOL_MAP[name] = (mod, fn)


@router.post("/tools/invoke")
async def invoke_tool(
    request: Request,
    auth: McpToolAuth = Depends(authenticate_mcp_tool_request),
):
    """
    Invoke an MCP tool by name. Body: { "tool": "qual_studies_list", "arguments": { ... } }.
    Auth: Authorization: Bearer <key> or X-API-Key: <key>.
    """
    _register_tools()
    t0 = time.perf_counter()

    def dur_ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    study_for_log: Optional[str] = None
    tool_name = ""

    try:
        try:
            body = await request.json()
        except Exception:
            _append_invocation_log(
                auth.store,
                auth=auth,
                tool_name="",
                study_id=None,
                status_code=400,
                duration_ms=dur_ms(),
                error_detail="Invalid JSON body",
            )
            raise HTTPException(status_code=400, detail="Invalid JSON body.")

        tool_name = body.get("tool") if isinstance(body, dict) else None
        arguments = body.get("arguments") if isinstance(body, dict) else {}
        if not isinstance(arguments, dict):
            arguments = {}
        study_for_log = arguments.get("study_id") if isinstance(arguments.get("study_id"), str) else None

        if not tool_name or tool_name not in _TOOL_MAP:
            detail = (
                f"Unknown tool. Use one of: {', '.join(sorted(_TOOL_MAP.keys()))}"
                if tool_name
                else "Missing tool name."
            )
            _append_invocation_log(
                auth.store,
                auth=auth,
                tool_name=str(tool_name or ""),
                study_id=study_for_log,
                status_code=400,
                duration_ms=dur_ms(),
                error_detail=detail[:500],
            )
            raise HTTPException(status_code=400, detail=detail)

        if not _tool_allowed(auth, tool_name):
            _append_invocation_log(
                auth.store,
                auth=auth,
                tool_name=tool_name,
                study_id=study_for_log,
                status_code=403,
                duration_ms=dur_ms(),
                error_detail="Tool not allowed for this API key scope",
            )
            raise HTTPException(
                status_code=403,
                detail="This API key is not allowed to invoke that tool.",
            )

        if not auth.from_env:
            sid_req = (study_for_log or "").strip()
            if not sid_req:
                _append_invocation_log(
                    auth.store,
                    auth=auth,
                    tool_name=tool_name,
                    study_id=None,
                    status_code=403,
                    duration_ms=dur_ms(),
                    error_detail="Missing study_id for study-scoped API key",
                )
                raise HTTPException(
                    status_code=403,
                    detail="This API key is study-scoped: include a string study_id in arguments.",
                )

        if not _study_allowed(auth, study_for_log):
            _append_invocation_log(
                auth.store,
                auth=auth,
                tool_name=tool_name,
                study_id=study_for_log,
                status_code=403,
                duration_ms=dur_ms(),
                error_detail="Study not allowed for this API key",
            )
            raise HTTPException(
                status_code=403,
                detail="This API key is not allowed to use that study.",
            )

        logger.info(
            "tool_invoke tool=%s study_id=%s user=%s",
            tool_name,
            study_for_log,
            getattr(auth.user, "email", auth.user.id),
        )
        mod, fn_name = _TOOL_MAP[tool_name]
        fn = getattr(mod, fn_name)
        call_args = _arguments_for_tool_fn(fn, arguments)
        try:
            with data_proxy_request_context(auth.data_proxy_enabled):
                if auth.data_proxy_enabled and tool_name in SENSITIVE_TOOLS:
                    result = invoke_and_mock(tool_name, **call_args)
                else:
                    result = fn(**call_args)
        except TypeError as e:
            _append_invocation_log(
                auth.store,
                auth=auth,
                tool_name=tool_name,
                study_id=study_for_log,
                status_code=400,
                duration_ms=dur_ms(),
                error_detail=str(e)[:500],
            )
            raise HTTPException(status_code=400, detail=f"Invalid arguments: {e}")

        try:
            out = json.loads(result)
        except json.JSONDecodeError:
            out = {"result": result}

        _append_invocation_log(
            auth.store,
            auth=auth,
            tool_name=tool_name,
            study_id=study_for_log,
            status_code=200,
            duration_ms=dur_ms(),
            error_detail=None,
        )
        return out

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("tool_invoke unexpected error tool=%s", tool_name)
        _append_invocation_log(
            auth.store,
            auth=auth,
            tool_name=tool_name or "",
            study_id=study_for_log,
            status_code=500,
            duration_ms=dur_ms(),
            error_detail=str(e)[:500],
        )
        raise


@router.get("/openapi.json")
async def get_openapi_spec(request: Request):
    """Return OpenAPI 3.0 spec for the tool API (for ChatGPT Custom GPT Actions)."""
    _register_tools()
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Research Workflow Tool API", "version": "1.0.0"},
        "paths": {
            "/v1/tools/invoke": {
                "post": {
                    "summary": "Invoke a tool",
                    "description": (
                        "Call any Research Workflow tool by name. Auth: Bearer token or X-API-Key. "
                        "Use env MCP_API_KEY / MCP_API_KEYS or an API key created in Platform admin."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["tool"],
                                    "properties": {
                                        "tool": {
                                            "type": "string",
                                            "description": "Tool name (e.g. qual_studies_list)",
                                        },
                                        "arguments": {"type": "object", "description": "Tool arguments"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Tool result (JSON)"}},
                }
            }
        },
    }
    return spec
