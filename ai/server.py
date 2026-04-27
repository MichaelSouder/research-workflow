"""
MCP server: registers all Research Workflow tools and runs over stdio.
Context (store, user) must be set before running (see __main__.py).
"""

from mcp.server.fastmcp import FastMCP

from ai.proxy import invoke_and_mock
from ai.proxy.defaults import SENSITIVE_TOOLS
from ai.proxy_env import is_proxy_enabled
from ai.resources import get_component_spec, get_pipeline_definition, get_study_overview, get_study_summary
from ai.tools import box_grid, components, config, distribution, pipelines, run, status, studies

mcp = FastMCP(
    "Research Workflow",
    json_response=True,
)

# --- Resources (read-only context for LLM) ---
@mcp.resource("study://default/overview")
def resource_study_overview() -> str:
    """List all studies the user has access to with roles."""
    return get_study_overview()


@mcp.resource("study://{study_id}/summary")
def resource_study_summary(study_id: str) -> str:
    """Study info, pipelines count, run status, distribution status."""
    return get_study_summary(study_id)


@mcp.resource("study://{study_id}/pipeline/{pipeline_id}")
def resource_pipeline(study_id: str, pipeline_id: str) -> str:
    """Full pipeline definition (nodes, edges)."""
    return get_pipeline_definition(study_id, pipeline_id)


@mcp.resource("spec://pipeline/components")
def resource_component_spec() -> str:
    """Pipeline component architecture, execution contract, port types, and custom code sandbox standards."""
    return get_component_spec()


# --- Studies ---
@mcp.tool()
def qual_studies_list() -> str:
    """List all studies the current user has access to, with role (viewer, editor, admin)."""
    if is_proxy_enabled() and "qual_studies_list" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_studies_list")
    return studies.qual_studies_list()


@mcp.tool()
def qual_study_get(study_id: str) -> str:
    """Get a single study by id. Returns id, name, description, role."""
    if is_proxy_enabled() and "qual_study_get" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_get", study_id=study_id)
    return studies.qual_study_get(study_id)


@mcp.tool()
def qual_study_users_list(study_id: str) -> str:
    """List users and their roles for a study. Requires admin."""
    if is_proxy_enabled() and "qual_study_users_list" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_users_list", study_id=study_id)
    return studies.qual_study_users_list(study_id)


@mcp.tool()
def qual_study_create(
    name: str,
    description: str | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create a new study. Caller must be admin of at least one study. Set confirm_dangerous_operation=true to proceed."""
    return studies.qual_study_create(name, description, confirm_dangerous_operation)


@mcp.tool()
def qual_study_update(
    study_id: str,
    name: str | None = None,
    description: str | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update study name and/or description. Requires admin. Set confirm_dangerous_operation=true to proceed."""
    return studies.qual_study_update(study_id, name, description, confirm_dangerous_operation)


@mcp.tool()
def qual_study_delete(study_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Delete a study. Requires admin. Fails if run in progress. Set confirm_dangerous_operation=true to proceed."""
    return studies.qual_study_delete(study_id, confirm_dangerous_operation)


@mcp.tool()
def qual_study_users_set(
    study_id: str,
    users: list[dict],
    confirm_dangerous_operation: bool = False,
) -> str:
    """Set user roles for study. users: [{\"user_id\": \"...\", \"role\": \"editor\"}, ...]. Replaces existing. Set confirm_dangerous_operation=true to proceed."""
    return studies.qual_study_users_set(study_id, users, confirm_dangerous_operation)


@mcp.tool()
def qual_study_user_add(
    study_id: str,
    email: str,
    role: str = "viewer",
    confirm_dangerous_operation: bool = False,
) -> str:
    """Add a user to the study by email. role: viewer, editor, or admin. Set confirm_dangerous_operation=true to proceed."""
    return studies.qual_study_user_add(study_id, email, role, confirm_dangerous_operation)


# --- Pipelines ---
@mcp.tool()
def qual_pipelines_list(study_id: str) -> str:
    """List pipelines for a study. Returns id, name, isDefault for each."""
    if is_proxy_enabled() and "qual_pipelines_list" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_pipelines_list", study_id=study_id)
    return pipelines.qual_pipelines_list(study_id)


@mcp.tool()
def qual_pipeline_get(study_id: str, pipeline_id: str = "__default__") -> str:
    """Get full pipeline definition (nodes, edges) for a study. Use pipeline_id='__default__' for default."""
    if is_proxy_enabled() and "qual_pipeline_get" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_pipeline_get", study_id=study_id, pipeline_id=pipeline_id)
    return pipelines.qual_pipeline_get(study_id, pipeline_id)


@mcp.tool()
def qual_pipeline_create(
    study_id: str,
    name: str,
    is_default: bool = False,
    nodes: list | None = None,
    edges: list | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create a new pipeline for the study. Set confirm_dangerous_operation=true to proceed."""
    return pipelines.qual_pipeline_create(study_id, name, is_default, nodes, edges, confirm_dangerous_operation)


@mcp.tool()
def qual_pipeline_update(
    study_id: str,
    pipeline_id: str,
    name: str,
    is_default: bool = False,
    nodes: list | None = None,
    edges: list | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create or update a pipeline. Cannot overwrite __default__. Set confirm_dangerous_operation=true to proceed."""
    return pipelines.qual_pipeline_update(study_id, pipeline_id, name, is_default, nodes, edges, confirm_dangerous_operation)


@mcp.tool()
def qual_pipeline_delete(
    study_id: str,
    pipeline_id: str,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Delete a pipeline. Cannot delete __default__. Set confirm_dangerous_operation=true to proceed."""
    return pipelines.qual_pipeline_delete(study_id, pipeline_id, confirm_dangerous_operation)


# --- Config ---
@mcp.tool()
def qual_study_config_get(study_id: str, reveal_secrets: bool = False) -> str:
    """Get study config (keys and values). Secrets are masked unless reveal_secrets is true."""
    if is_proxy_enabled() and "qual_study_config_get" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_config_get", study_id=study_id, reveal_secrets=reveal_secrets)
    return config.qual_study_config_get(study_id, reveal_secrets)


@mcp.tool()
def qual_config_get(reveal_secrets: bool = False) -> str:
    """Get merged config for the first study the user has access to. Secrets masked unless reveal_secrets."""
    if is_proxy_enabled() and "qual_config_get" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_config_get", reveal_secrets=reveal_secrets)
    return config.qual_config_get(reveal_secrets)


@mcp.tool()
def qual_study_config_set(
    study_id: str,
    config: dict,
    persist: bool = True,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update config for a study. config: key-value dict. Set confirm_dangerous_operation=true to proceed."""
    return config.qual_study_config_set(study_id, config, persist, confirm_dangerous_operation)


@mcp.tool()
def qual_config_set(
    config: dict,
    persist: bool = True,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update config for the first study (legacy). Set confirm_dangerous_operation=true to proceed."""
    return config.qual_config_set(config, persist, confirm_dangerous_operation)


# --- Status / activity ---
@mcp.tool()
def qual_status(study_id: str | None = None) -> str:
    """Get run status. If study_id is given, returns status only when active run is for that study."""
    if is_proxy_enabled() and "qual_status" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_status", study_id=study_id)
    return status.qual_status(study_id)


@mcp.tool()
def qual_study_status(study_id: str) -> str:
    """Get run status for a specific study."""
    if is_proxy_enabled() and "qual_study_status" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_status", study_id=study_id)
    return status.qual_study_status(study_id)


@mcp.tool()
def qual_activity(study_id: str | None = None) -> str:
    """Get activity log. If study_id given, returns activity only when active run is for that study."""
    if is_proxy_enabled() and "qual_activity" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_activity", study_id=study_id)
    return status.qual_activity(study_id)


@mcp.tool()
def qual_study_activity(study_id: str) -> str:
    """Get activity log for a specific study."""
    if is_proxy_enabled() and "qual_study_activity" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_activity", study_id=study_id)
    return status.qual_study_activity(study_id)


@mcp.tool()
def qual_study_errors(study_id: str) -> str:
    """Get errors (and warnings) from the activity log for a study."""
    if is_proxy_enabled() and "qual_study_errors" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_study_errors", study_id=study_id)
    return status.qual_study_errors(study_id)


# --- Run ---
@mcp.tool()
def qual_run_start(
    study_id: str,
    pipeline_id: str | None = None,
    config_overrides: dict | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Start the pipeline for this study. Set confirm_dangerous_operation=true to proceed."""
    return run.qual_run_start(study_id, pipeline_id, config_overrides, confirm_dangerous_operation)


@mcp.tool()
def qual_run_stop(study_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Stop the pipeline run for this study. Set confirm_dangerous_operation=true to proceed."""
    return run.qual_run_stop(study_id, confirm_dangerous_operation)


# --- Distribution ---
@mcp.tool()
def qual_distribution_contacts(study_id: str) -> str:
    """List mailing list contacts for the study (index, name, email, embeddedData)."""
    if is_proxy_enabled() and "qual_distribution_contacts" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_contacts", study_id=study_id)
    return distribution.qual_distribution_contacts(study_id)


@mcp.tool()
def qual_distribution_check(study_id: str) -> str:
    """Validate survey, mailing list, and message IDs for the study."""
    if is_proxy_enabled() and "qual_distribution_check" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_check", study_id=study_id)
    return distribution.qual_distribution_check(study_id)


@mcp.tool()
def qual_distribution_status(study_id: str) -> str:
    """Return whether a send is in progress and the last send result for the study."""
    if is_proxy_enabled() and "qual_distribution_status" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_status", study_id=study_id)
    return distribution.qual_distribution_status(study_id)


@mcp.tool()
def qual_distribution_list(study_id: str) -> str:
    """List email and SMS distributions for the survey/mailing list."""
    if is_proxy_enabled() and "qual_distribution_list" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_list", study_id=study_id)
    return distribution.qual_distribution_list(study_id)


@mcp.tool()
def qual_distribution_send_preview(study_id: str) -> str:
    """Preview which contacts would receive a send (no actual send)."""
    if is_proxy_enabled() and "qual_distribution_send_preview" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_send_preview", study_id=study_id)
    return distribution.qual_distribution_send_preview(study_id)


@mcp.tool()
def qual_distribution_export(study_id: str, format: str = "json") -> str:
    """Export survey responses. format: 'json' or 'csv'. Returns path to the exported file."""
    if is_proxy_enabled() and "qual_distribution_export" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_distribution_export", study_id=study_id, format=format)
    return distribution.qual_distribution_export(study_id, format)


@mcp.tool()
def qual_distribution_send(
    study_id: str,
    limit: int | None = None,
    contact_indices: list[int] | None = None,
    bypass_time_slot: bool = False,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Start sending distributions in the background. Set confirm_dangerous_operation=true to proceed."""
    return distribution.qual_distribution_send(study_id, limit, contact_indices, bypass_time_slot, confirm_dangerous_operation)


@mcp.tool()
def qual_distribution_delete_unsent(
    study_id: str,
    index: int | None = None,
    contact_id: str | None = None,
    all_unsent: bool = False,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Delete unsent distributions. Use exactly one of: index, contact_id, or all_unsent. Set confirm_dangerous_operation=true to proceed."""
    return distribution.qual_distribution_delete_unsent(study_id, index, contact_id, all_unsent, confirm_dangerous_operation)


@mcp.tool()
def qual_distribution_contact_patch(
    study_id: str,
    contact_id: str,
    embedded_data: dict,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update contact embedded data. Set confirm_dangerous_operation=true to proceed."""
    return distribution.qual_distribution_contact_patch(study_id, contact_id, embedded_data, confirm_dangerous_operation)


# --- Box / Grid ---
@mcp.tool()
def qual_box_folders(study_id: str | None = None, root: str = "0") -> str:
    """List Box folders. Pass study_id to use that study's Box config; root is folder id (default '0')."""
    if is_proxy_enabled() and "qual_box_folders" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_box_folders", study_id=study_id, root=root)
    return box_grid.qual_box_folders(study_id, root)


@mcp.tool()
def qual_study_box_config_status(study_id: str) -> str:
    """Return whether Box config is stored for this study (no secret content)."""
    return box_grid.qual_study_box_config_status(study_id)


@mcp.tool()
def qual_grid_studies(study_id: str | None = None) -> str:
    """List Grid studies. Pass study_id to use that study's config."""
    if is_proxy_enabled() and "qual_grid_studies" in SENSITIVE_TOOLS:
        return invoke_and_mock("qual_grid_studies", study_id=study_id)
    return box_grid.qual_grid_studies(study_id)


@mcp.tool()
def qual_box_config_set(
    study_id: str,
    config: dict,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Store Box JWT config for the study. Set confirm_dangerous_operation=true to proceed."""
    return box_grid.qual_box_config_set(study_id, config, confirm_dangerous_operation)


# --- Pipeline components (specs, list, get, run_debug) ---
@mcp.tool()
def qual_components_list() -> str:
    """List all registered pipeline components. Returns id, label, category, inputs, outputs, config_keys, source for each."""
    return components.qual_components_list()


@mcp.tool()
def qual_component_get(component_id: str) -> str:
    """Get full manifest for a component by id (e.g. qualtrics, process, grid, box)."""
    return components.qual_component_get(component_id)


@mcp.tool()
def qual_component_run_debug(
    code: str,
    inputs_json: str = "{}",
    config_json: str = "{}",
    timeout_seconds: int = 30,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Run custom component code in the sandbox with sample inputs (no pipeline run). Code uses pipeline.input(port_id), pipeline.config(key), pipeline.output(port_id, value), pipeline.log(msg). inputs_json and config_json are JSON objects. When data proxy is enabled, outputs are masked for AI users and confirm_dangerous_operation must be true."""
    if is_proxy_enabled() and "qual_component_run_debug" in SENSITIVE_TOOLS:
        return invoke_and_mock(
            "qual_component_run_debug",
            code=code,
            inputs_json=inputs_json,
            config_json=config_json,
            timeout_seconds=timeout_seconds,
            confirm_dangerous_operation=confirm_dangerous_operation,
        )
    return components.qual_component_run_debug(
        code, inputs_json, config_json, timeout_seconds, confirm_dangerous_operation
    )


@mcp.tool()
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
    """Create a new custom pipeline component. component_id: unique id (letters, numbers, underscore). inputs/outputs: lists of {id, label?, type?, required?} or {id, label?, type?}. handles_sensitive_data: set true if the component handles PII (masked for AI when proxy enabled). Set confirm_dangerous_operation=true to proceed."""
    return components.qual_component_create(
        component_id, label, code, description, category,
        inputs, outputs, config_keys, handles_sensitive_data, confirm_dangerous_operation,
    )


@mcp.tool()
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
    """Update an existing custom component. Only provided fields are updated. handles_sensitive_data: set true/false if the component handles PII (masked for AI when proxy enabled). Set confirm_dangerous_operation=true to proceed."""
    return components.qual_component_update(
        component_id, label, description, category,
        inputs, outputs, config_keys, handles_sensitive_data, code, confirm_dangerous_operation,
    )


@mcp.tool()
def qual_component_delete(component_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Delete a custom pipeline component. Cannot delete built-ins. Set confirm_dangerous_operation=true to proceed."""
    return components.qual_component_delete(component_id, confirm_dangerous_operation)
