"""SHA-256 hash for stored MCP / tool API keys (pepper optional via MCP_API_KEY_PEPPER)."""

from __future__ import annotations

import hashlib
import os
from typing import Optional


def normalize_allowed_study_ids(ids: Optional[list[str]]) -> list[str]:
    """Dedupe non-empty study ids; empty list means all studies allowed."""
    if not ids:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for x in ids:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def hash_mcp_api_secret(plaintext: str) -> str:
    pepper = (os.environ.get("MCP_API_KEY_PEPPER") or "").strip()
    return hashlib.sha256(f"{pepper}{plaintext}".encode("utf-8")).hexdigest()
