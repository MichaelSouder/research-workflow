"""Generate mock data from a schema+stats descriptor (same structure, safe values)."""

from __future__ import annotations

import random
import uuid
from typing import Any

try:
    from faker import Faker
except ImportError:
    Faker = None  # type: ignore[misc, assignment]

from ai.proxy.schema import infer_schema_and_stats

# Faker instance (lazy) for names, emails, phones.
_faker: "Faker | None" = None


def _get_faker(seed: int | None = None) -> "Faker | None":
    global _faker
    if Faker is None:
        return None
    if _faker is None:
        _faker = Faker()
    if seed is not None:
        _faker.seed_instance(seed)
    return _faker


def _mock_string(schema: dict[str, Any], index: int, seed: int | None) -> str:
    fmt = schema.get("format")
    length_min = schema.get("length_min", 0)
    length_max = schema.get("length_max", 20)
    length_max = max(length_max, length_min, 1)
    faker = _get_faker(seed)
    if fmt == "email" and faker:
        return f"sample_{index}@example.com" if seed is not None else faker.email()
    if fmt == "uuid":
        return str(uuid.uuid4())
    if fmt == "phone" and faker:
        return f"+1555000{index:04d}" if seed is not None else faker.phone_number()[:20]
    if fmt == "date":
        return "2024-01-15"
    if faker and (length_max > 10 or fmt is None):
        if seed is not None:
            return f"sample_value_{index}"
        return faker.text(max_nb_chars=min(length_max, 50))[:length_max]
    n = random.randint(length_min, length_max) if length_min <= length_max else length_max
    return "x" * max(1, min(n, 100))


def _mock_scalar(schema: dict[str, Any], index: int, seed: int | None) -> Any:
    t = schema.get("type", "string")
    if t == "null":
        return None
    if t == "boolean":
        return random.choice([True, False])
    if t == "integer":
        lo = schema.get("min", 0)
        hi = schema.get("max", 100)
        if lo == hi:
            lo = int(lo) - 3
            hi = int(hi) + 3
        return random.randint(int(lo), int(hi)) if lo <= hi else lo
    if t == "number":
        lo = schema.get("min", 0)
        hi = schema.get("max", 100)
        if lo == hi:
            lo = float(lo) - 3.0
            hi = float(hi) + 3.0
        return random.uniform(float(lo), float(hi)) if lo <= hi else lo
    if t == "string":
        return _mock_string(schema, index, seed)
    return ""


def _mock_value(schema: dict[str, Any], index: int, row_limit: int, seed: int | None) -> Any:
    t = schema.get("type", "string")
    if t == "array":
        length = min(schema.get("length", 0), row_limit)
        item_schema = schema.get("item", {"type": "string"})
        return [
            _mock_value(item_schema, i, row_limit, (seed + i) if seed is not None else None)
            for i in range(length)
        ]
    if t == "object":
        keys = schema.get("keys") or {}
        return {
            k: _mock_value(v, index, row_limit, seed)
            for k, v in keys.items()
        }
    return _mock_scalar(schema, index, seed)


def generate_mock(
    real_response: Any,
    row_limit: int = 50,
    seed: int | None = None,
) -> Any:
    """
    Build a mock response with the same structure as real_response.
    real_response is used only to infer schema; it is not copied or returned.
    Arrays are capped at row_limit. seed makes output deterministic.
    """
    if seed is not None:
        random.seed(seed)
    schema = infer_schema_and_stats(real_response)
    return _mock_value(schema, 0, row_limit, seed)
