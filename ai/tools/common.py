"""Shared helpers for tools: study access check, confirmation, and JSON result formatting."""

import json
import os
from typing import Any

from backend.datastore.base import STUDY_ROLE_VIEWER, Datastore, User

from ai.constants import CONFIRM_MESSAGE, DANGEROUS_TOOLS, PROXY_REQUIRES_CONFIRM_TOOLS


def require_study_access(
    store: Datastore, user: User, study_id: str, min_role: str = STUDY_ROLE_VIEWER
) -> str | None:
    """
    Return None if user has at least min_role for study; else return error message string.
    """
    study = store.get_study(study_id)
    if not study:
        return "Study not found"
    role = store.get_user_study_role(user.id, study_id)
    if not role:
        return "No access to this study"
    order = {STUDY_ROLE_VIEWER: 0, "editor": 1, "admin": 2}
    if order.get(role, -1) < order.get(min_role, 0):
        return "Insufficient permission"
    return None


def tool_result(data: Any) -> str:
    """Return JSON string for tool result (success)."""
    return json.dumps(data, indent=2)


def tool_error(message: str, detail: str | None = None) -> str:
    """Return JSON string for tool error."""
    out = {"error": message}
    if detail:
        out["detail"] = detail
    return json.dumps(out, indent=2)


def require_confirm(tool_name: str, confirm_dangerous_operation: bool) -> str | None:
    """
    If tool is dangerous (or proxy-only confirm tool when proxy is on) and not confirmed,
    return error JSON string; else return None.
    """
    from ai.proxy_env import is_proxy_enabled

    proxy_extra = is_proxy_enabled() and tool_name in PROXY_REQUIRES_CONFIRM_TOOLS
    if tool_name not in DANGEROUS_TOOLS and not proxy_extra:
        return None
    allowed = os.environ.get("MCP_ALLOWED_DANGEROUS_TOOLS", "").strip()
    if allowed and tool_name in DANGEROUS_TOOLS:
        if tool_name not in [t.strip() for t in allowed.split(",") if t.strip()]:
            return tool_error("This dangerous tool is not in the allowlist (MCP_ALLOWED_DANGEROUS_TOOLS).")
    if not confirm_dangerous_operation:
        return tool_error(CONFIRM_MESSAGE)
    return None
