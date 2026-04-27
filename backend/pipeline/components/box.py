"""
Box component: upload files to Box folders per record.
Inputs: records (with subject_id, event_id), processed_store (from upstream default port).
Outputs: records (pass-through).
"""

import logging
import os

from backend.pipeline.components.base import (
    ComponentManifest,
    OutputPort,
    PORT_TYPE_RECORDS,
    RunContext,
)
from backend.pipeline.box_client import BoxClient
from backend.pipeline.config import VIDEOS_DIR

MANIFEST = ComponentManifest(
    id="box",
    label="Box",
    description="Upload files to Box folders.",
    category="sinks",
    inputs=[],
    outputs=[
        OutputPort("records", "Records (pass-through)", PORT_TYPE_RECORDS),
        OutputPort("processed_store", "Processed store (pass-through)", "blob"),
    ],
    config_keys=["BOX_ROOT_FOLDER_ID", "BOX_CONFIG_PATH"],
    source="builtin",
)


def run(inputs: dict, config: dict, context: RunContext) -> dict:
    """Create Box folders and upload videos per record; update processed_store."""
    log = context.logger or logging.getLogger(__name__)
    data = inputs.get("default") or {}
    records = list(data.get("records") or [])
    processed_store = data.get("processed_store")

    box_root = (config.get("BOX_ROOT_FOLDER_ID") or "").strip()
    box_config_path = config.get("BOX_CONFIG_PATH") or ""
    if not box_config_path:
        from backend.pipeline.config import BOX_CONFIG_PATH
        box_config_path = BOX_CONFIG_PATH
    if not box_root:
        raise ValueError("BOX_ROOT_FOLDER_ID is required")

    log.info("--- Box: Connecting and listing root ---")
    cl = BoxClient(box_config_path)
    log.info("Box: Root folder %s", cl.list_folders())
    log.info("Box: Listing folder items for root %s", box_root)
    cl.list_folder_items(box_root)

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

        sub_id = record.get("subject_id") or record.get("responseId", "unknown")
        evt_id = record.get("event_id", "unknown")
        folder_name = f"sub-{sub_id}_evt-{evt_id}_test-2"
        log.info("Box: Creating folder '%s' under root %s", folder_name, box_root)
        folder = cl.create_folder(box_root, folder_name)
        target_folder_id = getattr(folder, "object_id", None) or getattr(folder, "id", None) or box_root

        first_file_id = record.get("QID362_FILE_ID")
        second_file_id = record.get("QID363_FILE_ID")
        if first_file_id:
            video_one_name = f"{first_file_id}.mp4"
            video_one_path = os.path.join(VIDEOS_DIR, video_one_name)
            log.info("Box: Uploading %s to folder %s", video_one_name, target_folder_id)
            cl.upload(target_folder_id, video_one_path, video_one_name)
        if second_file_id:
            video_two_name = f"{second_file_id}.mp4"
            video_two_path = os.path.join(VIDEOS_DIR, video_two_name)
            log.info("Box: Uploading %s to folder %s", video_two_name, target_folder_id)
            cl.upload(target_folder_id, video_two_path, video_two_name)

        if processed_store is not None and record.get("responseId") and record.get("event_id"):
            processed_store.add(record["responseId"])
        log.info("--- Pipeline completed successfully. Processed 1 record(s). ---")
        break  # One record per run (match original behavior)

    if processed_store is not None:
        processed_store.save()
        log.info("Duplicate detection: saved %s processed response ID(s) to store.", len(processed_store))

    return {
        "records": records,
        "processed_store": processed_store,
    }
