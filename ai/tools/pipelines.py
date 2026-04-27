"""Pipeline tools: list/get (read-only) and create/update/delete (dangerous, require confirm)."""

from backend.datastore.base import DEFAULT_PIPELINE_ID
from backend.pipeline_validation import validate_pipeline
from backend.services import pipeline_events as pipeline_events_service

from ai.constants import PROXY_BLOCKS_PIPELINE_UPDATE_DELETE_MESSAGE
from ai.context import get_store, get_user
from ai.proxy_env import is_proxy_enabled
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result


def qual_pipelines_list(study_id: str) -> str:
    """List pipelines for a study. Returns id, name, isDefault for each."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        pipelines = store.list_pipelines(study_id)
        out = [
            {"id": p.id, "name": p.name, "isDefault": p.is_default}
            for p in pipelines
        ]
        return tool_result({"pipelines": out})
    except Exception as e:
        return tool_error(str(e))


def qual_pipeline_get(study_id: str, pipeline_id: str) -> str:
    """Get full pipeline definition (nodes, edges) for a study. Use pipeline_id='__default__' for default."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        pid = pipeline_id or DEFAULT_PIPELINE_ID
        pipeline = store.get_pipeline(study_id, pid)
        if not pipeline:
            return tool_error("Pipeline not found")
        return tool_result({
            "id": pipeline.id,
            "name": pipeline.name,
            "isDefault": pipeline.is_default,
            "nodes": pipeline.nodes,
            "edges": pipeline.edges,
        })
    except Exception as e:
        return tool_error(str(e))


def qual_pipeline_create(
    study_id: str,
    name: str,
    is_default: bool = False,
    nodes: list | None = None,
    edges: list | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create a new pipeline for the study. Returns pipeline id. Requires confirmation."""
    err = require_confirm("qual_pipeline_create", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        n = nodes if nodes is not None else []
        e = edges if edges is not None else []
        validate_pipeline(n, e)
        pipeline_id = store.create_pipeline(study_id, name, is_default, n, e)
        pipeline = store.get_pipeline(study_id, pipeline_id)
        if pipeline:
            pipeline_events_service.publish(
                study_id,
                pipeline_id,
                "created",
                {"name": pipeline.name, "nodes": pipeline.nodes, "edges": pipeline.edges},
            )
        return tool_result({"ok": True, "id": pipeline_id, "message": "Pipeline created."})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_pipeline_update(
    study_id: str,
    pipeline_id: str,
    name: str,
    is_default: bool = False,
    nodes: list | None = None,
    edges: list | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create or update a pipeline. nodes and edges required. Cannot overwrite __default__. Requires confirmation."""
    if is_proxy_enabled():
        return tool_error(PROXY_BLOCKS_PIPELINE_UPDATE_DELETE_MESSAGE)
    err = require_confirm("qual_pipeline_update", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if pipeline_id == DEFAULT_PIPELINE_ID:
            return tool_error("Cannot overwrite the default pipeline id.")
        n = nodes if nodes is not None else []
        e = edges if edges is not None else []
        validate_pipeline(n, e)
        store.set_pipeline(study_id, pipeline_id, name, is_default, n, e)
        pipeline_events_service.publish(
            study_id,
            pipeline_id,
            "updated",
            {"name": name, "nodes": n, "edges": e},
        )
        return tool_result({"ok": True, "id": pipeline_id, "message": "Pipeline saved."})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_pipeline_delete(
    study_id: str,
    pipeline_id: str,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Delete a pipeline. Cannot delete __default__. Requires confirmation."""
    if is_proxy_enabled():
        return tool_error(PROXY_BLOCKS_PIPELINE_UPDATE_DELETE_MESSAGE)
    err = require_confirm("qual_pipeline_delete", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if pipeline_id == DEFAULT_PIPELINE_ID:
            return tool_error("Cannot delete the default pipeline.")
        existing = store.get_pipeline(study_id, pipeline_id)
        if not existing:
            return tool_error("Pipeline not found")
        was_default = existing.is_default
        store.delete_pipeline(study_id, pipeline_id)
        pipeline_events_service.publish(study_id, pipeline_id, "deleted", {})
        if was_default:
            default_id = store.get_default_pipeline_id(study_id)
            return tool_result({"ok": True, "message": "Pipeline deleted. Default is now: " + (default_id or DEFAULT_PIPELINE_ID)})
        return tool_result({"ok": True, "message": "Pipeline deleted."})
    except Exception as e:
        return tool_error(str(e))
