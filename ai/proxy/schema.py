"""Infer JSON schema and value stats from a real response for mock generation."""

from __future__ import annotations

import re
from typing import Any

# Max array elements to sample when inferring item schema (avoid scanning huge lists).
MAX_ARRAY_SAMPLE = 100


def _typeof(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _string_format(s: str) -> str | None:
    """Heuristic: email, uuid, date-ish, or generic."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", s):
        return "email"
    if re.match(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", s
    ):
        return "uuid"
    if re.match(r"^\d{4}-\d{2}-\d{2}", s) or re.match(r"^\d{2}/\d{2}/\d{4}", s):
        return "date"
    if re.match(r"^\+?[\d\s\-()]{10,}$", s):
        return "phone"
    return None


def _infer_scalar(value: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"type": _typeof(value)}
    if isinstance(value, (int, float)):
        out["min"] = value
        out["max"] = value
    elif isinstance(value, str):
        out["length_min"] = len(value)
        out["length_max"] = len(value)
        fmt = _string_format(value)
        if fmt:
            out["format"] = fmt
    elif isinstance(value, bool):
        out["value"] = value
    return out


def _merge_scalar_stats(acc: dict[str, Any], value: Any) -> None:
    t = _typeof(value)
    if acc.get("type") != t:
        acc["type"] = t
    if isinstance(value, (int, float)):
        acc["min"] = min(acc.get("min", value), value)
        acc["max"] = max(acc.get("max", value), value)
    elif isinstance(value, str):
        L = len(value)
        acc["length_min"] = min(acc.get("length_min", L), L)
        acc["length_max"] = max(acc.get("length_max", L), L)
        fmt = _string_format(value)
        if fmt and "format" not in acc:
            acc["format"] = fmt


def _infer_object(obj: dict[str, Any], depth: int) -> dict[str, Any]:
    if depth <= 0:
        return {"type": "object", "keys": {}}
    keys: dict[str, Any] = {}
    for k, v in obj.items():
        keys[k] = infer_schema_and_stats(v, depth - 1)
    return {"type": "object", "keys": keys}


def _infer_array(arr: list[Any], depth: int) -> dict[str, Any]:
    if depth <= 0:
        return {"type": "array", "length": len(arr), "item": {"type": "string"}}
    sample = arr[:MAX_ARRAY_SAMPLE]
    item_schemas = [infer_schema_and_stats(x, depth - 1) for x in sample if x is not None]
    if not item_schemas:
        return {"type": "array", "length": len(arr), "item": {"type": "string"}}
    # Merge first item schema with stats from others
    item = item_schemas[0].copy()
    for s in item_schemas[1:]:
        if s.get("type") == "object" and "keys" in s and item.get("type") == "object":
            for key, key_schema in (s.get("keys") or {}).items():
                if key not in (item.get("keys") or {}):
                    (item.setdefault("keys", {}))[key] = key_schema
        elif (
            item.get("type") in ("string", "integer", "number", "boolean")
            and s.get("type") in ("string", "integer", "number", "boolean")
        ):
            _merge_scalar_stats(item, _scalar_from_schema(s))
    return {"type": "array", "length": len(arr), "item": item}


def _scalar_from_schema(s: dict[str, Any]) -> Any:
    """Fake a scalar value from schema for merging stats; used only for primitives."""
    t = s.get("type")
    if t == "string":
        return "x" * (s.get("length_max") or 10)
    if t == "integer":
        return s.get("min", 0) or s.get("max", 0)
    if t == "number":
        return float(s.get("min", 0) or s.get("max", 0))
    if t == "boolean":
        return s.get("value", True)
    return None


def infer_schema_and_stats(value: Any, max_depth: int = 10) -> dict[str, Any]:
    """
    Infer a schema + stats descriptor from a JSON-serializable value.
    Used to generate mocks with the same structure and value ranges.
    """
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, (int, float)):
        return {"type": "number" if isinstance(value, float) else "integer", "min": value, "max": value}
    if isinstance(value, str):
        fmt = _string_format(value)
        out: dict[str, Any] = {
            "type": "string",
            "length_min": len(value),
            "length_max": len(value),
        }
        if fmt:
            out["format"] = fmt
        return out
    if isinstance(value, list):
        return _infer_array(value, max_depth)
    if isinstance(value, dict):
        return _infer_object(value, max_depth)
    return {"type": "string"}
