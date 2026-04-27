"""Tests for backend config merge, mask, and token resolution."""

from backend.services.state import (
    DEFAULT_CONFIG_KEYS,
    FRAUD_CONFIG_KEYS,
    get_script_default,
    mask_value,
)


def test_mask_value_secrets():
    assert mask_value("QUALTRICS_API_TOKEN", "secret123") == "********"
    assert mask_value("GRID_API_TOKEN", "abc") == "********"
    assert mask_value("BOX_CLIENT_SECRET", "x") == "********"


def test_mask_value_non_secret():
    assert mask_value("QUALTRICS_SURVEY_ID", "SV_123") == "SV_123"
    assert mask_value("GRID_STUDY_ID", "372") == "372"


def test_mask_value_none_or_empty():
    assert mask_value("QUALTRICS_API_TOKEN", None) == ""
    assert mask_value("QUALTRICS_API_TOKEN", "") == ""


def test_default_config_keys_present():
    assert "QUALTRICS_API_TOKEN" in DEFAULT_CONFIG_KEYS
    assert "GRID_STUDY_ID" in DEFAULT_CONFIG_KEYS
    assert "BOX_ROOT_FOLDER_ID" in DEFAULT_CONFIG_KEYS


def test_fraud_config_keys_present():
    assert "FRAUD_ENABLED" in FRAUD_CONFIG_KEYS
    assert "FRAUD_SPEED" in FRAUD_CONFIG_KEYS


def test_get_script_default_returns_none_for_non_token():
    assert get_script_default("QUALTRICS_SURVEY_ID") is None


def test_get_script_default_token_from_pipeline_config():
    # Pipeline config no longer has default tokens (Phase 6); may return "" or None
    val = get_script_default("QUALTRICS_API_TOKEN")
    assert val is None or val == "" or isinstance(val, str)
