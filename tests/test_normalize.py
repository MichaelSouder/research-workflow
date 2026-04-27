"""Tests for pipeline.normalize.normalize_legacy_qualtrics_data."""

from backend.pipeline.normalize import normalize_legacy_qualtrics_data


def test_normalize_splits_name():
    data = [
        {"QID312_1": "John Doe", "responseId": "R1", "startDate": "x", "endDate": "y"},
    ]
    result = normalize_legacy_qualtrics_data(data)
    assert len(result) == 1
    assert result[0]["QID312_1"] == "John"
    assert result[0]["QID312_5"] == "Doe"
    assert result[0]["normalizedName"] == "John Doe"


def test_normalize_preserves_already_split():
    data = [
        {
            "QID312_1": "Jane",
            "QID312_5": "Smith",
            "responseId": "R2",
            "startDate": "x",
            "endDate": "y",
        },
    ]
    result = normalize_legacy_qualtrics_data(data)
    assert len(result) == 1
    assert result[0]["QID312_1"] == "Jane"
    assert result[0]["QID312_5"] == "Smith"
    assert result[0]["normalizedName"] == "Jane Smith"


def test_normalize_single_name_no_space():
    data = [
        {"QID312_1": "Only", "responseId": "R3", "startDate": "x", "endDate": "y"},
    ]
    result = normalize_legacy_qualtrics_data(data)
    assert len(result) == 1
    assert result[0]["QID312_1"] == "Only"
    assert result[0]["QID312_5"] == ""
    assert result[0]["normalizedName"] == "Only "


def test_normalize_filters_incomplete():
    data = [
        {"QID312_1": "A", "responseId": "R1", "startDate": "x", "endDate": "y"},
        {"QID312_1": "B"},  # no responseId
    ]
    result = normalize_legacy_qualtrics_data(data)
    assert len(result) == 1
    assert result[0]["responseId"] == "R1"
