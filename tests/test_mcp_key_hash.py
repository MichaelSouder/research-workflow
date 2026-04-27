"""Tests for MCP API key hashing and study allowlist normalization."""

from backend.mcp_key_hash import hash_mcp_api_secret, normalize_allowed_study_ids


def test_normalize_allowed_study_ids_empty():
    assert normalize_allowed_study_ids(None) == []
    assert normalize_allowed_study_ids([]) == []


def test_normalize_allowed_study_ids_dedupes_and_strips():
    assert normalize_allowed_study_ids(["a", "  a  ", "b", "b"]) == ["a", "b"]


def test_hash_mcp_api_secret_stable_for_empty_pepper():
    h = hash_mcp_api_secret("test-secret")
    assert len(h) == 64
    assert h == hash_mcp_api_secret("test-secret")
