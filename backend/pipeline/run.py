"""
Pipeline orchestration driven by graph step order and types.
Uses the component registry: each step type is a component with run(inputs, config, context) -> dict.
Runs only the node types in PIPELINE_STEP_TYPES (same order as PIPELINE_STEP_ORDER).
Default: qualtrics, process, grid, box (backward compatible).
"""

import logging
import os
from datetime import datetime

from backend.pipeline.components import get_runner, has_component
from backend.pipeline.components.base import RunContext
from backend.pipeline.logging_config import setup_pipeline_logging

log = logging.getLogger(__name__)

DEFAULT_STEP_TYPES = ["qualtrics", "process", "grid", "box"]


def _step_types_from_env() -> list[str]:
    raw = os.environ.get("PIPELINE_STEP_TYPES", "").strip()
    if not raw:
        return DEFAULT_STEP_TYPES
    return [t.strip() for t in raw.split(",") if t.strip()]


def _step_order_from_env() -> list[str] | None:
    """PIPELINE_STEP_ORDER is comma-separated node ids in topological order."""
    raw = os.environ.get("PIPELINE_STEP_ORDER", "").strip()
    if not raw:
        return None
    return [nid.strip() for nid in raw.split(",") if nid.strip()]


def _config_from_env() -> dict[str, str]:
    """Build config dict from os.environ for component run()."""
    keys = [
        "QUALTRICS_API_TOKEN",
        "QUALTRICS_SURVEY_ID",
        "QUALTRICS_DATA_CENTER",
        "DUPLICATE_SKIP_ENABLED",
        "PROCESSED_IDS_PATH",
        "FRAUD_ENABLED",
        "FRAUD_SPEED",
        "FRAUD_DUPLICATE_IP",
        "FRAUD_STRAIGHTLINING",
        "FRAUD_INCOMPLETE",
        "GRID_API_TOKEN",
        "GRID_STUDY_ID",
        "BOX_ROOT_FOLDER_ID",
        "BOX_CONFIG_PATH",
    ]
    return {k: (os.environ.get(k) or "") for k in keys}


def main() -> None:
    setup_pipeline_logging()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Pipeline started at %s", started)

    step_types = _step_types_from_env()
    step_order = _step_order_from_env()
    if not step_order or len(step_order) != len(step_types):
        step_order = [f"step_{i}" for i in range(len(step_types))]

    log.info("Step types (from graph): %s", step_types)

    if "qualtrics" not in step_types:
        log.warning("Qualtrics not in step types; no survey data. Add a Qualtrics source node to the pipeline.")
        return

    config = _config_from_env()
    context = RunContext(logger=log)

    previous_output: dict = {}
    last_component_id: str | None = None
    for i, component_id in enumerate(step_types):
        if not has_component(component_id):
            log.warning("Unknown component type %r; skipping.", component_id)
            continue

        if i == 0:
            inputs = {}
        else:
            inputs = {"default": previous_output}

        log.info("--- Running component: %s ---", component_id)
        runner = get_runner(component_id)
        try:
            previous_output = runner(inputs, config, context)
            last_component_id = component_id
        except Exception as e:
            log.exception("Component %s failed: %s", component_id, e)
            raise

    # If last step was process (no grid/box), save processed_store so duplicate tracking is persisted
    if last_component_id == "process":
        ps = previous_output.get("processed_store") if previous_output else None
        if ps is not None and hasattr(ps, "save"):
            try:
                ps.save()
                log.info("Duplicate detection: saved processed response ID(s) to store.")
            except Exception as e:
                log.warning("Could not save processed_store: %s", e)


if __name__ == "__main__":
    main()
