"""MCP data proxy env flag + optional per-request override (HTTP tool API)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Optional

PROXY_ENABLED_ENV = "MCP_DATA_PROXY_ENABLED"
TOOL_API_ENV_PROXY_ENV = "TOOL_API_ENV_KEY_DATA_PROXY"
"""If unset or truthy, env-based MCP_API_KEY(s) use data proxy. Set to 0/false/no to disable."""

_request_data_proxy: ContextVar[Optional[bool]] = ContextVar("request_data_proxy", default=None)


def is_proxy_enabled() -> bool:
    """
    Return True if MCP_DATA_PROXY_ENABLED is set to a truthy value, unless a request-level
    override is active (HTTP tool API sets this via data_proxy_request_context).
    """
    override = _request_data_proxy.get()
    if override is not None:
        return bool(override)
    val = (os.environ.get(PROXY_ENABLED_ENV) or "").strip().lower()
    return val in ("1", "true", "yes")


def env_key_data_proxy_default() -> bool:
    """Default data-proxy policy for MCP_API_KEY / MCP_API_KEYS auth (no owner user row)."""
    v = (os.environ.get(TOOL_API_ENV_PROXY_ENV) or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


@contextmanager
def data_proxy_request_context(enabled: bool) -> Generator[None, None, None]:
    """Force is_proxy_enabled() to enabled for the duration (used by /v1/tools/invoke)."""
    token = _request_data_proxy.set(enabled)
    try:
        yield
    finally:
        _request_data_proxy.reset(token)
