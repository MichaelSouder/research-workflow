"""Run tools: start and stop pipeline (dangerous, require confirm)."""

from backend.datastore.base import DEFAULT_PIPELINE_ID
from backend.pipeline_validation import validate_pipeline
from backend.services import state

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result


def qual_run_start(
    study_id: str,
    pipeline_id: str | None = None,
    config_overrides: dict | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Start the pipeline for this study. Optional pipeline_id; otherwise uses default. Requires confirmation."""
    err = require_confirm("qual_run_start", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if state.is_running():
            return tool_error("Pipeline already running.")
        config = store.get_study_config(study_id)
        overrides = config_overrides or {}
        if overrides:
            config = {**config, **{k: v for k, v in overrides.items() if v not in (None, "", "********")}}
        env = state.get_config_for_pipeline(config)
        if not (env.get("QUALTRICS_API_TOKEN") and env.get("GRID_API_TOKEN")):
            missing = [k for k in ("QUALTRICS_API_TOKEN", "GRID_API_TOKEN") if not env.get(k)]
            return tool_error(f"Missing required tokens: {', '.join(missing)}. Set them in Connections, then try Start again.")
        pid = pipeline_id or store.get_default_pipeline_id(study_id) or DEFAULT_PIPELINE_ID
        pipeline = store.get_pipeline(study_id, pid)
        step_order = None
        step_types = None
        if pipeline:
            try:
                step_order = validate_pipeline(pipeline.nodes, pipeline.edges)
            except ValueError:
                step_order = [n.get("id") for n in pipeline.nodes if n.get("id")]
            if step_order and pipeline.nodes:
                node_by_id = {n.get("id"): n for n in pipeline.nodes if n.get("id")}
                # Use node id as component id when type is "stage"; else use type (e.g. qualtrics, process).
                step_types = []
                for sid in step_order:
                    node = node_by_id.get(sid, {})
                    t = node.get("type", "stage")
                    step_types.append(sid if t == "stage" else t)
        state.run_pipeline(
            study_id=study_id,
            config_dict=config,
            datastore=store,
            step_order=step_order,
            step_types=step_types,
        )
        return tool_result({"ok": True, "message": "Pipeline started."})
    except Exception as e:
        return tool_error(str(e))


def qual_run_stop(study_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Stop the pipeline run for this study. Requires confirmation."""
    err = require_confirm("qual_run_stop", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        ok, message = state.request_stop(study_id)
        if not ok:
            return tool_error(message)
        return tool_result({"ok": True, "message": message})
    except Exception as e:
        return tool_error(str(e))
