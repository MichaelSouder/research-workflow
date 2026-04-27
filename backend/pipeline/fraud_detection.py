"""
Basic fraud/integrity detection for Qualtrics survey data.

Use with Qualtrics export JSON (responses list). Run detect_fraud() on loaded
responses to get a report of flagged response IDs and reasons.

Example:
    from backend.pipeline.fraud_detection import load_qualtrics_responses, detect_fraud

    responses = load_qualtrics_responses("backend/workspace/qualtrics/export.json")
    report = detect_fraud(responses)
    print(report.summary)
    for rid, flags in report.by_response.items():
        if flags:
            print(rid, flags)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# --- Constants for Qualtrics value keys --------------------------------------

KEY_DURATION = "duration"
KEY_PROGRESS = "progress"
KEY_FINISHED = "finished"
KEY_IP = "ipAddress"
KEY_RESPONSE_ID = "responseId"
KEY_VALUES = "values"

# --- Config -------------------------------------------------------------------


@dataclass
class FraudDetectionConfig:
    """Thresholds and options for fraud checks."""

    min_duration_seconds: float = 60.0
    """Flag if duration (seconds) is below this (e.g. survey too short)."""

    duplicate_ip_max_count: int = 1
    """Flag IPs that appear in more than this many completed responses."""

    straightline_ratio: float = 0.85
    """Flag if the same value appears in this fraction of scorable items (0-1)."""

    straightline_min_items: int = 5
    """Only run straightline check when there are at least this many scorable items."""

    include_incomplete: bool = True
    """If True, run checks on all responses; if False, only on finished=1."""

    def __post_init__(self) -> None:
        if not 0 <= self.straightline_ratio <= 1:
            raise ValueError("straightline_ratio must be between 0 and 1")


# --- Report -------------------------------------------------------------------


@dataclass
class FraudReport:
    """Result of running fraud detection on Qualtrics responses."""

    by_response: dict[str, list[str]] = field(default_factory=dict)
    """Maps responseId -> list of flag reasons (e.g. 'speed', 'duplicate_ip')."""

    by_ip: dict[str, list[str]] = field(default_factory=dict)
    """Maps IP -> list of responseIds (for duplicate IP context)."""

    summary: dict[str, Any] = field(default_factory=dict)
    """Aggregate counts: total, flagged, by flag type."""

    def is_flagged(self, response_id: str) -> bool:
        return bool(self.by_response.get(response_id))

    def get_flags(self, response_id: str) -> list[str]:
        return self.by_response.get(response_id, [])


# --- Load ---------------------------------------------------------------------


def load_qualtrics_responses(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """
    Load Qualtrics export JSON and return the list of response objects.

    Expects JSON with a top-level "responses" key. Each element has
    "responseId", "values", and optionally "labels", "displayedFields", etc.
    """
    path = os.path.abspath(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "responses" not in data:
        raise ValueError('JSON must contain a "responses" key')
    return data["responses"]


def responses_from_export_data(export_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Get responses list from an already-loaded Qualtrics export dict."""
    if "responses" not in export_data:
        raise ValueError('Export data must contain a "responses" key')
    return export_data["responses"]


# --- Checks --------------------------------------------------------------------


def _get(response: dict[str, Any], key: str, default: Any = None) -> Any:
    """Get value from response['values'] with optional default."""
    values = response.get(KEY_VALUES) or {}
    return values.get(key, default)


def _check_speed(
    response: dict[str, Any],
    config: FraudDetectionConfig,
) -> bool:
    """True if response should be flagged for suspiciously short duration."""
    duration = _get(response, KEY_DURATION)
    if duration is None:
        return False
    try:
        sec = float(duration)
    except (TypeError, ValueError):
        return False
    return sec < config.min_duration_seconds


def _check_incomplete(response: dict[str, Any]) -> bool:
    """True if response is not finished (progress < 100 or finished != 1)."""
    progress = _get(response, KEY_PROGRESS)
    finished = _get(response, KEY_FINISHED)
    if progress is not None:
        try:
            if float(progress) < 100:
                return True
        except (TypeError, ValueError):
            pass
    if finished is not None and finished != 1 and str(finished).lower() not in ("1", "true"):
        return True
    return False


def _check_straightlining(
    response: dict[str, Any],
    config: FraudDetectionConfig,
) -> bool:
    """
    True if the same numeric/choice value is used for a large fraction of
    scorable items (matrix / single-choice style QID fields).
    """
    values = response.get(KEY_VALUES) or {}
    # Collect QID* values that look like scalars (numbers or short codes)
    scores: list[Any] = []
    for k, v in values.items():
        if not k.startswith("QID") or k.endswith("_TEXT") or "FILE_ID" in k:
            continue
        if v is None or v == "":
            continue
        # Normalize to string for comparison; keep numeric as-is for mode
        try:
            scores.append(float(v))
        except (TypeError, ValueError):
            scores.append(str(v).strip())
    if len(scores) < config.straightline_min_items:
        return False
    if not scores:
        return False
    # Most common value
    from collections import Counter

    (most_common_val, count) = Counter(scores).most_common(1)[0]
    ratio = count / len(scores)
    return ratio >= config.straightline_ratio


def _build_ip_to_response_ids(
    responses: list[dict[str, Any]],
    config: FraudDetectionConfig,
) -> dict[str, list[str]]:
    """Map IP -> list of responseIds (only completed if not include_incomplete)."""
    by_ip: dict[str, list[str]] = {}
    for r in responses:
        if not config.include_incomplete and _check_incomplete(r):
            continue
        ip = _get(r, KEY_IP)
        rid = r.get(KEY_RESPONSE_ID)
        if ip is None or rid is None:
            continue
        ip_str = str(ip).strip()
        if ip_str:
            by_ip.setdefault(ip_str, []).append(rid)
    return by_ip


def _run_checks(
    responses: list[dict[str, Any]],
    config: FraudDetectionConfig,
) -> FraudReport:
    """Run all checks and return a FraudReport."""
    by_response: dict[str, list[str]] = {}
    for r in responses:
        rid = r.get(KEY_RESPONSE_ID)
        if not rid:
            continue
        rid_str = str(rid)
        flags: list[str] = []

        if _check_incomplete(r):
            flags.append("incomplete")

        if config.include_incomplete or "incomplete" not in flags:
            if _check_speed(r, config):
                flags.append("speed")
            if _check_straightlining(r, config):
                flags.append("straightlining")

        if flags:
            by_response[rid_str] = flags

    # Duplicate IP: flag responses whose IP appears more than duplicate_ip_max_count times
    by_ip = _build_ip_to_response_ids(responses, config)
    duplicate_ips = {
        ip: rids for ip, rids in by_ip.items() if len(rids) > config.duplicate_ip_max_count
    }
    for ip, rids in duplicate_ips.items():
        for rid in rids:
            by_response.setdefault(rid, []).append("duplicate_ip")
        # Deduplicate flag list
        by_response.update({rid: list(dict.fromkeys(by_response[rid])) for rid in rids})

    # Summary
    flag_counts: dict[str, int] = {}
    for flags in by_response.values():
        for f in flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1

    total = len(responses)
    flagged_count = len(by_response)
    summary = {
        "total_responses": total,
        "flagged_count": flagged_count,
        "flag_counts": flag_counts,
        "duplicate_ips": list(duplicate_ips.keys()),
    }

    return FraudReport(
        by_response=by_response,
        by_ip=dict(duplicate_ips),
        summary=summary,
    )


# --- Public API ---------------------------------------------------------------


def detect_fraud(
    responses: list[dict[str, Any]] | str | os.PathLike[str],
    config: FraudDetectionConfig | None = None,
) -> FraudReport:
    """
    Run fraud/integrity checks on Qualtrics responses.

    Args:
        responses: Either a list of response dicts (each with "responseId", "values"),
                   or a path to a Qualtrics export JSON file.
        config: Optional thresholds; uses defaults if None.

    Returns:
        FraudReport with by_response, by_ip, and summary.
    """
    if config is None:
        config = FraudDetectionConfig()

    if isinstance(responses, (str, os.PathLike)):
        responses = load_qualtrics_responses(responses)

    return _run_checks(responses, config)


def filter_flagged_response_ids(
    report: FraudReport,
    exclude_flags: list[str] | None = None,
) -> set[str]:
    """
    Return set of response IDs that have at least one flag.
    If exclude_flags is given, only count those flags (e.g. ['speed', 'duplicate_ip']).
    """
    if exclude_flags is None:
        return {rid for rid, flags in report.by_response.items() if flags}
    exclude = set(exclude_flags)
    return {rid for rid, flags in report.by_response.items() if exclude and (exclude & set(flags))}
