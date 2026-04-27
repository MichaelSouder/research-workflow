"""Tests for pipeline.qualtrics_distribution (config parsing, timezone, time slots)."""

import json
import os

import pytest

from backend.pipeline.qualtrics_distribution import (
    _config,
    _embedded_flag,
    _parse_time_slots,
    _validate_timezone,
    check_ids,
    get_contact_list,
    list_distributions,
    send_preview,
)


def test_config_merge_from_override():
    override = {"QUALTRICS_SURVEY_ID": "SV_custom", "QUALTRICS_DATA_CENTER": "ca1"}
    c = _config(override)
    assert c.get("QUALTRICS_SURVEY_ID") == "SV_custom"
    assert c.get("QUALTRICS_DATA_CENTER") == "ca1"


def test_config_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("QUALTRICS_MAILING_LIST_ID", "ML_abc")
    c = _config({})
    assert c.get("QUALTRICS_MAILING_LIST_ID") == "ML_abc"


def test_validate_timezone_valid():
    _validate_timezone("America/Chicago")
    _validate_timezone("UTC")
    _validate_timezone("Europe/London")


def test_validate_timezone_invalid():
    with pytest.raises(ValueError, match="Invalid timezone"):
        _validate_timezone("Not/ATimezone")
    with pytest.raises(ValueError, match="empty"):
        _validate_timezone("")


def test_parse_time_slots_empty():
    assert _parse_time_slots("") == []
    assert _parse_time_slots("[]") == []


def test_parse_time_slots_valid():
    assert _parse_time_slots("[[800,900],[1200,1300]]") == [(800, 900), (1200, 1300)]
    assert _parse_time_slots("[[0,2359]]") == [(0, 2359)]


def test_parse_time_slots_invalid():
    with pytest.raises(ValueError, match="JSON"):
        _parse_time_slots("not json")
    with pytest.raises(ValueError, match="array"):
        _parse_time_slots("{}")
    with pytest.raises(ValueError, match="start must be less"):
        _parse_time_slots("[[900,800]]")
    with pytest.raises(ValueError, match="0-2400"):
        _parse_time_slots("[[10000,11000]]")


def test_check_ids_missing_config():
    result = check_ids({"QUALTRICS_API_TOKEN": "test-token"})
    assert result["ok"] is False
    assert "QUALTRICS_SURVEY_ID" in str(result["errors"]) or "empty" in str(result["errors"]).lower()


def test_get_contact_list_requires_directory_and_mailing_list():
    with pytest.raises(ValueError, match="QUALTRICS_DIRECTORY_ID|QUALTRICS_MAILING_LIST_ID"):
        get_contact_list({"QUALTRICS_API_TOKEN": "test-token"})
    with pytest.raises(ValueError, match="QUALTRICS_DIRECTORY_ID|QUALTRICS_MAILING_LIST_ID"):
        get_contact_list({"QUALTRICS_API_TOKEN": "test-token", "QUALTRICS_DIRECTORY_ID": "DIR_1"})


def test_embedded_flag():
    assert _embedded_flag({}, "SurveysSchedule") == ""
    assert _embedded_flag({"SurveysSchedule": "0"}, "SurveysSchedule") == "0"
    assert _embedded_flag({"UseSMS": "1"}, "UseSMS") == "1"
    assert _embedded_flag({"DeleteUnsent": 1}, "DeleteUnsent") == "1"


def test_list_distributions_returns_structure():
    # With empty survey_id we still get email/sms keys (errors from API when survey_id missing)
    result = list_distributions({"QUALTRICS_API_TOKEN": "test-token", "QUALTRICS_SURVEY_ID": ""})
    assert "email" in result
    assert "sms" in result
    assert "errors" in result
    assert isinstance(result["email"], list)
    assert isinstance(result["sms"], list)


def test_send_preview_requires_timezone():
    with pytest.raises(ValueError, match="Invalid timezone|Timezone"):
        send_preview({"QUALTRICS_DISTRIBUTION_TIMEZONE": "Not/ATimezone"})
