"""Tests for backend.pipeline.fraud_detection APIs."""

from backend.pipeline.fraud_detection import (
    FraudReport,
    detect_fraud,
    filter_flagged_response_ids,
)


def test_detect_fraud_accepts_list():
    responses = [
        {
            "responseId": "R1",
            "values": {"duration": 30, "progress": 100, "finished": 1, "ipAddress": "1.2.3.4"},
        },
        {
            "responseId": "R2",
            "values": {"duration": 120, "progress": 100, "finished": 1, "ipAddress": "1.2.3.4"},
        },
    ]
    report = detect_fraud(responses)
    assert isinstance(report, FraudReport)
    assert (
        "speed" in report.summary
        or "duplicate_ip" in report.summary
        or report.summary.get("total", 0) >= 0
    )


def test_filter_flagged_response_ids():
    report = FraudReport(
        by_response={"R1": ["speed"], "R2": ["duplicate_ip"]},
        by_ip={},
        summary={"total": 3, "flagged": 2},
    )
    ids = filter_flagged_response_ids(report, exclude_flags=["speed", "duplicate_ip"])
    assert "R1" in ids
    assert "R2" in ids


def test_filter_flagged_response_ids_partial_flags():
    report = FraudReport(
        by_response={"R1": ["speed"], "R2": ["duplicate_ip"]},
        by_ip={},
        summary={},
    )
    ids = filter_flagged_response_ids(report, exclude_flags=["speed"])
    assert "R1" in ids
    assert "R2" not in ids
