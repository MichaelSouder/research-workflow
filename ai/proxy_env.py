"""MCP data proxy env flag (kept outside ai.proxy to avoid import cycles with ai.tools)."""

import os

PROXY_ENABLED_ENV = "MCP_DATA_PROXY_ENABLED"


def is_proxy_enabled() -> bool:
    """Return True if MCP_DATA_PROXY_ENABLED is set to a truthy value."""
    val = (os.environ.get(PROXY_ENABLED_ENV) or "").strip().lower()
    return val in ("1", "true", "yes")
