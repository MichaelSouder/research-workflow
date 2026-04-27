"""
Process component: normalize, duplicate skip, fraud detection.
Inputs: videos_info, export_path (from upstream default port).
Outputs: records, processed_store.
"""

import logging
from pathlib import Path

from backend.pipeline.components.base import (
    ComponentManifest,
    OutputPort,
    PORT_TYPE_BLOB,
    PORT_TYPE_RECORDS,
    RunContext,
)
from backend.pipeline.normalize import normalize_legacy_qualtrics_data
from backend.pipeline.processed_store import ProcessedStore

MANIFEST = ComponentManifest(
    id="process",
    label="Process",
    description="Normalize, duplicate skip, and fraud detection.",
    category="processing",
    inputs=[],  # Receives upstream via default port
    outputs=[
        OutputPort("records", "Normalized records", PORT_TYPE_RECORDS),
        OutputPort("processed_store", "Processed ID store (for downstream)", PORT_TYPE_BLOB),
    ],
    config_keys=[
        "DUPLICATE_SKIP_ENABLED",
        "PROCESSED_IDS_PATH",
        "FRAUD_ENABLED",
        "FRAUD_SPEED",
        "FRAUD_DUPLICATE_IP",
        "FRAUD_STRAIGHTLINING",
        "FRAUD_INCOMPLETE",
    ],
    source="builtin",
    handles_sensitive_data=True,
)


def run(inputs: dict, config: dict, context: RunContext) -> dict:
    """Normalize, dedupe, and fraud-filter. Reads videos_info and export_path from inputs['default']."""
    log = context.logger or logging.getLogger(__name__)
    data = inputs.get("default") or {}
    videos_info = data.get("videos_info") or []
    export_json_path = data.get("export_path") or ""

    log.info("--- Normalizing records (names, completion) ---")
    normalized_records = normalize_legacy_qualtrics_data(videos_info)
    log.info("Normalized %s complete record(s) for processing", len(normalized_records))

    processed_store = None
    dup_enabled = (config.get("DUPLICATE_SKIP_ENABLED") or "true").lower() in ("1", "true", "yes")
    if dup_enabled:
        path_str = config.get("PROCESSED_IDS_PATH") or ""
        if not path_str:
            from backend.pipeline.config import PROCESSED_IDS_PATH
            path_str = PROCESSED_IDS_PATH
        processed_store = ProcessedStore(Path(path_str))
        before = len(normalized_records)
        normalized_records = [
            r for r in normalized_records if not processed_store.contains(r.get("responseId", ""))
        ]
        skipped = before - len(normalized_records)
        if skipped:
            log.info(
                "Duplicate detection: skipping %s already-processed response(s); %s record(s) to process.",
                skipped,
                len(normalized_records),
            )

    fraud_enabled = (config.get("FRAUD_ENABLED") or "true").lower() in ("1", "true", "yes")
    if fraud_enabled and normalized_records and export_json_path:
        try:
            from backend.pipeline.fraud_detection import (
                detect_fraud,
                filter_flagged_response_ids,
            )

            report = detect_fraud(export_json_path)
            enabled_flags = []
            if (config.get("FRAUD_SPEED") or "true").lower() in ("1", "true", "yes"):
                enabled_flags.append("speed")
            if (config.get("FRAUD_DUPLICATE_IP") or "true").lower() in ("1", "true", "yes"):
                enabled_flags.append("duplicate_ip")
            if (config.get("FRAUD_STRAIGHTLINING") or "true").lower() in ("1", "true", "yes"):
                enabled_flags.append("straightlining")
            if (config.get("FRAUD_INCOMPLETE") or "true").lower() in ("1", "true", "yes"):
                enabled_flags.append("incomplete")
            if enabled_flags:
                flagged_ids = filter_flagged_response_ids(report, exclude_flags=enabled_flags)
                before = len(normalized_records)
                normalized_records = [
                    r for r in normalized_records if r.get("responseId") not in flagged_ids
                ]
                log.info(
                    "Fraud detection: skipped %s flagged response(s), %s record(s) remaining (checks: %s).",
                    before - len(normalized_records),
                    len(normalized_records),
                    ", ".join(enabled_flags),
                )
        except Exception as e:
            log.warning("Fraud detection skipped (error): %s", e)

    return {
        "records": normalized_records,
        "processed_store": processed_store,
    }
