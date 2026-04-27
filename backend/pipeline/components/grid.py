"""
Grid component: create subjects and events in Grid for each record.
Inputs: records, processed_store (from upstream default port).
Outputs: records (enriched with subject_id, event_id).
"""

import json
import logging
from datetime import datetime

from backend.pipeline.components.base import (
    ComponentManifest,
    OutputPort,
    PORT_TYPE_RECORDS,
    RunContext,
)
from backend.pipeline.grid_client import GridClient

MANIFEST = ComponentManifest(
    id="grid",
    label="Grid",
    description="Send subjects and events to Grid.",
    category="sinks",
    inputs=[],
    outputs=[
        OutputPort("records", "Records with subject_id and event_id", PORT_TYPE_RECORDS),
        OutputPort("processed_store", "Processed store (pass-through)", "blob"),
    ],
    config_keys=["GRID_API_TOKEN", "GRID_STUDY_ID", "BOX_ROOT_FOLDER_ID"],
    source="builtin",
)


def run(inputs: dict, config: dict, context: RunContext) -> dict:
    """Create Grid subjects/events per record; enrich records with subject_id, event_id."""
    log = context.logger or logging.getLogger(__name__)
    data = inputs.get("default") or {}
    records = list(data.get("records") or [])
    processed_store = data.get("processed_store")

    token = (config.get("GRID_API_TOKEN") or "").strip()
    study_id = (config.get("GRID_STUDY_ID") or "").strip()
    box_root = (config.get("BOX_ROOT_FOLDER_ID") or "").strip()
    if not token or not study_id:
        raise ValueError("GRID_API_TOKEN and GRID_STUDY_ID are required")

    grid_client = GridClient(token, study_id)
    total = len(records)
    for idx, record in enumerate(records, 1):
        first_name = (record.get("QID312_1") or "").capitalize()
        last_name = (record.get("QID312_5") or "").capitalize()
        log.info(
            "Processing record %s/%s — %s %s (response %s)",
            idx,
            total,
            first_name,
            last_name,
            record.get("responseId", "?"),
        )

        log.info("--- Grid: Looking up subjects and creating events ---")
        results = grid_client.subject_get_by_last_name(last_name)
        if results:
            log.info("Grid: Found existing subject(s) for %s %s: %s", first_name, last_name, results)

        created_subject = None
        created_evt = None
        if not results:
            log.info(
                "Grid: No existing subject for %s %s; creating subject and subject-study",
                first_name,
                last_name,
            )
            subject = grid_client._get_subject_template(
                0,
                first_name,
                last_name,
                datetime.now().strftime("%Y-%m-%d"),
                0, 0, 0, 0, 0, 0,
                "Auto-generated from automation script.",
            )
            created_subject = grid_client.subject_create(subject)
            log.info("Grid: Created subject id=%s", created_subject.get("id"))
            subject_study = grid_client._get_subject_study_template(
                created_subject["id"],
                "Registered by TicTech Bot.",
                0,
                datetime.now().strftime("%Y-%m-%d"),
                0,
                1,
            )
            grid_client.subject_study_create(subject_study)
            log.info("Grid: Created subject-study for subject id=%s", created_subject["id"])

            start_date = record.get("startDate", "")
            end_date = record.get("endDate", "")
            log.info("Grid: Creating event for subject id=%s (procedure 1)", created_subject["id"])
            evt = grid_client._get_event_template(
                created_subject["id"],
                1,
                start_date,
                end_date,
                0,
                0,
                "Video moved to Box.",
            )
            created_evt = grid_client.event_create(evt)
            log.info("Grid: Created event id=%s", created_evt.get("id"))

            json_data = {
                "folder": f"sub-{created_subject['id']}_evt-{created_evt['id']}_test-2",
                "root_folder_id": box_root,
            }
            evt_detail = grid_client._get_event_detail_template(
                "QualtricsVideoBoxArchive",
                created_evt["id"],
                1,
                json.dumps(json_data),
            )
            grid_client.event_details_create(created_evt["id"], evt_detail)

        if created_subject is None and results:
            created_subject = results[0] if isinstance(results[0], dict) else {"id": getattr(results[0], "id", None)}
        if created_evt is None and created_subject and results:
            # Already had subject; we didn't create event in this run
            pass

        record["subject_id"] = created_subject.get("id") if created_subject else None
        record["event_id"] = created_evt.get("id") if created_evt else None
        log.info("--- Grid completed for record. ---")
        break  # Process one record per run (match original behavior)

    return {
        "records": records,
        "processed_store": processed_store,
    }
