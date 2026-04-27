"""MCP resources: study overview, study summary, pipeline definition (read-only, no secrets)."""

import json

from backend.services import state

from ai.context import get_store, get_user
from ai.proxy.defaults import get_mock_seed, get_row_limit
from ai.proxy_env import is_proxy_enabled
from ai.proxy.mock_gen import generate_mock
from ai.tools.common import require_study_access, tool_error, tool_result


def _resource_result(name: str, payload: dict, study_id: str | None = None) -> str:
    """Return mock-safe resource payload when proxy mode is enabled."""
    if not is_proxy_enabled():
        return tool_result(payload)
    seed = get_mock_seed(name, study_id)
    mocked = generate_mock(payload, row_limit=get_row_limit(name), seed=seed)
    # Policy: keep real study names visible while mocking other fields.
    if isinstance(payload, dict) and isinstance(mocked, dict):
        if "studies" in payload and isinstance(payload.get("studies"), list) and isinstance(mocked.get("studies"), list):
            for i, real_item in enumerate(payload["studies"]):
                if i >= len(mocked["studies"]):
                    break
                if isinstance(real_item, dict) and isinstance(mocked["studies"][i], dict):
                    if "name" in real_item:
                        mocked["studies"][i]["name"] = real_item.get("name")
        if "study" in payload and isinstance(payload.get("study"), dict) and isinstance(mocked.get("study"), dict):
            if "name" in payload["study"]:
                mocked["study"]["name"] = payload["study"].get("name")
    return tool_result(mocked)


def get_study_overview() -> str:
    """List studies with roles (for resource study://default/overview)."""
    try:
        store = get_store()
        user = get_user()
        pairs = store.list_studies_for_user(user.id)
        studies = [
            {"id": s.id, "name": s.name, "description": s.description, "role": role}
            for s, role in pairs
        ]
        return _resource_result("resource_study_overview", {"studies": studies})
    except Exception as e:
        return tool_error(str(e))


def get_study_summary(study_id: str) -> str:
    """Study info + pipelines count + run status + distribution status (for resource study://{id}/summary)."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        study = store.get_study(study_id)
        if not study:
            return tool_error("Study not found")
        pipelines = store.list_pipelines(study_id)
        status_data = state.get_status(study_id)
        busy = state.get_distribution_busy(study_id)
        last = state.get_distribution_last_result(study_id)
        return _resource_result("resource_study_summary", {
            "study": {"id": study.id, "name": study.name, "description": study.description},
            "pipelinesCount": len(pipelines),
            "runStatus": status_data,
            "distributionBusy": busy,
            "distributionLastResult": last,
        }, study_id=study_id)
    except Exception as e:
        return tool_error(str(e))


def get_pipeline_definition(study_id: str, pipeline_id: str) -> str:
    """Full pipeline definition nodes/edges (for resource study://{id}/pipeline/{pipeline_id})."""
    try:
        from backend.datastore.base import DEFAULT_PIPELINE_ID

        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        pid = pipeline_id or DEFAULT_PIPELINE_ID
        pipeline = store.get_pipeline(study_id, pid)
        if not pipeline:
            return tool_error("Pipeline not found")
        return _resource_result("resource_pipeline_definition", {
            "id": pipeline.id,
            "name": pipeline.name,
            "isDefault": pipeline.is_default,
            "nodes": pipeline.nodes,
            "edges": pipeline.edges,
        }, study_id=study_id)
    except Exception as e:
        return tool_error(str(e))


def get_component_spec() -> str:
    """Return pipeline component architecture and standards (for resource spec://pipeline/components)."""
    return """# Pipeline Component Spec and Standards

## Execution contract
Every component implements: `run(inputs: dict, config: dict, context: RunContext) -> dict`
- **inputs**: Map from input port id to value (from upstream). First step gets empty dict; others get `inputs["default"]` = previous step's full output.
- **config**: Map of config key → value (env/study config).
- **context**: RunContext with logger, run_id, study_id, workspace_path, export_dir.
- **Returns**: Dict from output port id to value. Downstream receives this as `inputs["default"]`.

## Port data types
- `records`: list of dicts (e.g. survey responses).
- `file_path`: string path to a file.
- `blob`: arbitrary JSON-serializable value.
- `any`: no schema.

## Manifest fields (per component)
- id, label, description, category (sources | processing | sinks | integration | custom)
- inputs: list of { id, label?, type?, required? }
- outputs: list of { id, label?, type? }
- config_keys: list of config key names
- source: builtin | custom
- version: optional
- **handles_sensitive_data**: If true, this component's I/O may contain PII. When MCP_DATA_PROXY_ENABLED=1, such data is masked for AI users (e.g. qual_component_run_debug returns mocked outputs); the real app always uses unmasked data.

## Custom component sandbox (code blobs)
Custom code runs in an **isolated subprocess** with a **restricted API** only:
- `pipeline.input(port_id)` — read input value
- `pipeline.config(key)` — read config value
- `pipeline.output(port_id, value)` — set output (must be JSON-serializable)
- `pipeline.log(message)` — log line

**Not allowed**: import, open, os, subprocess, eval, exec, network, filesystem. Safe builtins only (len, str, list, dict, range, etc.). Timeout applies; process is killed on timeout.

## Built-in components (registry)
Use qual_components_list to list; qual_component_get(component_id) for full manifest.
Current: qualtrics (sources), process (processing), grid (sinks), box (sinks).

## Building custom components (MCP)
- **qual_component_create**: Create a new custom component (component_id, label, code, description?, category?, inputs?, outputs?, config_keys?, handles_sensitive_data?). Set handles_sensitive_data=true if the component processes PII. Requires confirm_dangerous_operation.
- **qual_component_update**: Update an existing custom component; only provided fields are updated. handles_sensitive_data?: true | false. Requires confirm_dangerous_operation.
- **qual_component_delete**: Delete a custom component. Cannot delete built-ins. Requires confirm_dangerous_operation.
- **qual_component_run_debug**: Run custom code in the sandbox with sample inputs (no pipeline run); use to test before adding to a pipeline. When MCP_DATA_PROXY_ENABLED=1, returned outputs are mocked so the AI never sees real sensitive data.
Custom components are stored under backend/custom_components/*.json by default (override with CUSTOM_COMPONENTS_DIR). After create/update/delete the registry reloads automatically.
"""
