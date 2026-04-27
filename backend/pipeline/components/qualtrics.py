"""
Qualtrics component: export survey responses and retrieve videos info.
Inputs: none (source).
Outputs: export_path (file_path), videos_info (records).
"""

from backend.pipeline.components.base import (
    ComponentManifest,
    InputPort,
    OutputPort,
    PORT_TYPE_FILE_PATH,
    PORT_TYPE_RECORDS,
    RunContext,
)


MANIFEST = ComponentManifest(
    id="qualtrics",
    label="Qualtrics",
    description="Export survey responses and media.",
    category="sources",
    inputs=[],
    outputs=[
        OutputPort("export_path", "Export file path", PORT_TYPE_FILE_PATH),
        OutputPort("videos_info", "Videos info records", PORT_TYPE_RECORDS),
    ],
    config_keys=[
        "QUALTRICS_API_TOKEN",
        "QUALTRICS_SURVEY_ID",
        "QUALTRICS_DATA_CENTER",
    ],
    source="builtin",
    handles_sensitive_data=True,
)


def run(inputs: dict, config: dict, context: RunContext) -> dict:
    """Export survey responses and retrieve videos info. No inputs required."""
    import logging

    from backend.pipeline.qualtrics_client import QualtricsClient

    log = context.logger or logging.getLogger(__name__)
    token = config.get("QUALTRICS_API_TOKEN", "").strip()
    survey_id = config.get("QUALTRICS_SURVEY_ID", "").strip()
    data_center = config.get("QUALTRICS_DATA_CENTER", "").strip() or "yul1"

    if not token or not survey_id:
        raise ValueError("QUALTRICS_API_TOKEN and QUALTRICS_SURVEY_ID are required")

    log.info("--- Qualtrics: Starting survey response export ---")
    qual = QualtricsClient(token, survey_id, data_center, "", "videos")
    export_json_path = qual.download_survey_responses()
    log.info("Qualtrics: Export saved to %s", export_json_path)

    log.info("--- Qualtrics: Retrieving videos info and downloading media ---")
    videos_info = qual.retrieve_videos_info(
        [
            "Registrant ID",
            "QID312_1",
            "QID312_5",
            "startDate",
            "endDate",
        ],
        export_json_path,
        True,
    )
    log.info("Qualtrics: Retrieved %s response(s) with video info", len(videos_info))

    return {
        "export_path": export_json_path,
        "videos_info": videos_info,
    }
