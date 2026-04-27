"""MCP tools for pipeline components: list, get, create, update, delete, run_debug."""

import json
import logging

from ai.tools.common import require_confirm, tool_error, tool_result

logger = logging.getLogger(__name__)


def qual_components_list() -> str:
    """List all registered pipeline components (built-in and custom). Returns id, label, category, inputs, outputs, config_keys, source for each."""
    try:
        from backend.pipeline.components import list_components

        components = list_components()
        out = []
        for c in components:
            out.append({
                "id": c.id,
                "label": c.label,
                "description": c.description,
                "category": c.category,
                "inputs": [{"id": p.id, "label": p.label, "type": p.type, "required": p.required} for p in c.inputs],
                "outputs": [{"id": p.id, "label": p.label, "type": p.type} for p in c.outputs],
                "config_keys": c.config_keys,
                "source": c.source,
                "version": c.version,
                "handles_sensitive_data": getattr(c, "handles_sensitive_data", False),
            })
        return tool_result({"components": out})
    except Exception as e:
        logger.exception("qual_components_list failed")
        return tool_error(str(e))


def qual_component_get(component_id: str) -> str:
    """Get full manifest for a component by id. Use for pipeline node types: qualtrics, process, grid, box (and custom when added)."""
    try:
        from backend.pipeline.components import get_manifest

        manifest = get_manifest(component_id)
        if not manifest:
            return tool_error(f"Component not found: {component_id!r}")
        return tool_result({
            "id": manifest.id,
            "label": manifest.label,
            "description": manifest.description,
            "category": manifest.category,
            "inputs": [{"id": p.id, "label": p.label, "type": p.type, "required": p.required} for p in manifest.inputs],
            "outputs": [{"id": p.id, "label": p.label, "type": p.type} for p in manifest.outputs],
            "config_keys": manifest.config_keys,
            "source": manifest.source,
            "version": manifest.version,
            "handles_sensitive_data": getattr(manifest, "handles_sensitive_data", False),
        })
    except Exception as e:
        logger.exception("qual_component_get failed")
        return tool_error(str(e))


def qual_component_run_debug(
    code: str,
    inputs_json: str = "{}",
    config_json: str = "{}",
    timeout_seconds: int = 30,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Run custom component code in the sandbox with sample inputs (no pipeline run). Use to test/debug custom node code. code: Python using pipeline.input(port_id), pipeline.config(key), pipeline.output(port_id, value), pipeline.log(msg). inputs_json and config_json are JSON objects. Returns outputs dict or error. When MCP_DATA_PROXY_ENABLED=1, confirm_dangerous_operation must be true."""
    err = require_confirm("qual_component_run_debug", confirm_dangerous_operation)
    if err:
        return err
    try:
        inputs = json.loads(inputs_json) if inputs_json.strip() else {}
        config = json.loads(config_json) if config_json.strip() else {}
    except json.JSONDecodeError as e:
        return tool_error(f"Invalid JSON in inputs or config: {e}")

    try:
        from backend.pipeline.components.base import RunContext
        from backend.pipeline.components.sandbox import run_custom_component

        context = RunContext(logger=logger)
        outputs = run_custom_component(
            code=code,
            inputs=inputs,
            config=config,
            context=context,
            timeout_seconds=min(max(1, timeout_seconds), 300),
        )
        return tool_result({"outputs": outputs})
    except RuntimeError as e:
        return tool_error(str(e))
    except Exception as e:
        logger.exception("qual_component_run_debug failed")
        return tool_error(str(e))


def qual_component_create(
    component_id: str,
    label: str,
    code: str,
    description: str = "",
    category: str = "custom",
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
    config_keys: list[str] | None = None,
    handles_sensitive_data: bool = False,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create a new custom pipeline component. component_id: unique id (letters, numbers, underscore). inputs/outputs: lists of {id, label?, type?, required?} (inputs) or {id, label?, type?} (outputs). handles_sensitive_data: set true if the component handles PII/sensitive data (masked for AI when proxy enabled). Use confirm_dangerous_operation=true to proceed."""
    err = require_confirm("qual_component_create", confirm_dangerous_operation)
    if err:
        return err
    try:
        from backend.pipeline.components.base import ComponentManifest, InputPort, OutputPort
        from backend.pipeline.components.custom_store import save_custom_component
        from backend.pipeline.components import reload_custom_components

        inputs = inputs or [{"id": "default", "type": "any", "required": True}]
        outputs = outputs or [{"id": "default", "type": "any"}]
        config_keys = config_keys or []
        in_ports = [
            InputPort(
                id=p["id"],
                label=p.get("label"),
                type=p.get("type", "any"),
                required=p.get("required", True),
            )
            for p in inputs
        ]
        out_ports = [
            OutputPort(id=p["id"], label=p.get("label"), type=p.get("type", "any"))
            for p in outputs
        ]
        manifest = ComponentManifest(
            id=component_id,
            label=label,
            description=description,
            category=category,
            inputs=in_ports,
            outputs=out_ports,
            config_keys=config_keys,
            source="custom",
            handles_sensitive_data=handles_sensitive_data,
        )
        save_custom_component(component_id, manifest, code)
        reload_custom_components()
        return tool_result({"ok": True, "message": f"Custom component {component_id!r} created.", "id": component_id})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        logger.exception("qual_component_create failed")
        return tool_error(str(e))


def qual_component_update(
    component_id: str,
    label: str | None = None,
    description: str | None = None,
    category: str | None = None,
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
    config_keys: list[str] | None = None,
    handles_sensitive_data: bool | None = None,
    code: str | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update an existing custom component. Only provided fields are updated. handles_sensitive_data: set true/false to mark component as handling PII (masked for AI when proxy enabled). Set confirm_dangerous_operation=true to proceed."""
    err = require_confirm("qual_component_update", confirm_dangerous_operation)
    if err:
        return err
    try:
        from backend.pipeline.components.base import ComponentManifest, InputPort, OutputPort
        from backend.pipeline.components.custom_store import load_custom_component, save_custom_component
        from backend.pipeline.components import reload_custom_components

        loaded = load_custom_component(component_id)
        if not loaded:
            return tool_error(f"Custom component not found: {component_id!r}")
        manifest, existing_code = loaded
        new_code = code if code is not None else existing_code
        new_inputs = manifest.inputs
        if inputs is not None:
            new_inputs = [
                InputPort(
                    id=p["id"],
                    label=p.get("label"),
                    type=p.get("type", "any"),
                    required=p.get("required", True),
                )
                for p in inputs
            ]
        new_outputs = manifest.outputs
        if outputs is not None:
            new_outputs = [
                OutputPort(id=p["id"], label=p.get("label"), type=p.get("type", "any"))
                for p in outputs
            ]
        new_handles_sensitive = (
            handles_sensitive_data if handles_sensitive_data is not None else getattr(manifest, "handles_sensitive_data", False)
        )
        new_manifest = ComponentManifest(
            id=manifest.id,
            label=label if label is not None else manifest.label,
            description=description if description is not None else manifest.description,
            category=category if category is not None else manifest.category,
            inputs=new_inputs,
            outputs=new_outputs,
            config_keys=config_keys if config_keys is not None else manifest.config_keys,
            source="custom",
            version=manifest.version,
            handles_sensitive_data=new_handles_sensitive,
        )
        save_custom_component(component_id, new_manifest, new_code)
        reload_custom_components()
        return tool_result({"ok": True, "message": f"Custom component {component_id!r} updated.", "id": component_id})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        logger.exception("qual_component_update failed")
        return tool_error(str(e))


def qual_component_delete(component_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Delete a custom pipeline component. Cannot delete built-in components. Set confirm_dangerous_operation=true to proceed."""
    err = require_confirm("qual_component_delete", confirm_dangerous_operation)
    if err:
        return err
    try:
        from backend.pipeline.components.custom_store import delete_custom_component
        from backend.pipeline.components import reload_custom_components

        deleted = delete_custom_component(component_id)
        if not deleted:
            return tool_error(f"Custom component not found or built-in: {component_id!r}")
        reload_custom_components()
        return tool_result({"ok": True, "message": f"Custom component {component_id!r} deleted.", "id": component_id})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        logger.exception("qual_component_delete failed")
        return tool_error(str(e))
