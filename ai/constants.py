"""Tool names and sandbox constants. Dangerous tools require confirm_dangerous_operation."""

# When MCP_DATA_PROXY_ENABLED=1, these tools also require confirm_dangerous_operation (see require_confirm).
PROXY_REQUIRES_CONFIRM_TOOLS = frozenset({
    "qual_component_run_debug",
})

# Tools that modify data or have high impact; require confirm_dangerous_operation=True
DANGEROUS_TOOLS = frozenset({
    "qual_study_create",
    "qual_study_update",
    "qual_study_delete",
    "qual_study_config_set",
    "qual_pipeline_create",
    "qual_pipeline_update",
    "qual_pipeline_delete",
    "qual_run_start",
    "qual_run_stop",
    "qual_study_users_set",
    "qual_study_user_add",
    "qual_distribution_send",
    "qual_distribution_delete_unsent",
    "qual_distribution_contact_patch",
    "qual_box_config_set",
    "qual_config_set",
    "qual_component_create",
    "qual_component_update",
    "qual_component_delete",
})

CONFIRM_MESSAGE = (
    "Dangerous operation not confirmed. Set confirm_dangerous_operation to true to proceed."
)

PROXY_BLOCKS_PIPELINE_UPDATE_DELETE_MESSAGE = (
    "Data proxy mode (MCP_DATA_PROXY_ENABLED) does not allow updating or deleting existing "
    "pipelines. Disable the proxy or use a session without the proxy to modify or remove pipelines."
)
