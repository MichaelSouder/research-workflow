"""Data proxy configuration: which tools are mocked, row limits, and feature flag."""

from ai.proxy_env import PROXY_ENABLED_ENV, is_proxy_enabled

# Tools that return sensitive data; when proxy is enabled, their responses are replaced with mocks.
SENSITIVE_TOOLS = frozenset({
    "qual_studies_list",
    "qual_study_get",
    "qual_study_users_list",
    "qual_distribution_contacts",
    "qual_distribution_list",
    "qual_distribution_send_preview",
    "qual_distribution_export",
    "qual_pipelines_list",
    "qual_pipeline_get",
    "qual_study_activity",
    "qual_study_errors",
    "qual_status",
    "qual_study_status",
    "qual_activity",
    "qual_study_config_get",
    "qual_config_get",
    "qual_distribution_check",
    "qual_distribution_status",
    "qual_box_folders",
    "qual_grid_studies",
    "qual_component_run_debug",
})

# Default max rows to emit in mock arrays (e.g. contacts, activity).
DEFAULT_ROW_LIMITS: dict[str, int] = {
    "qual_distribution_contacts": 50,
    "qual_study_users_list": 20,
    "qual_studies_list": 20,
    "qual_study_activity": 30,
    "qual_study_errors": 20,
    "qual_distribution_send_preview": 50,
    "qual_distribution_list": 20,
    "qual_pipelines_list": 10,
    "qual_box_folders": 30,
    "qual_grid_studies": 20,
    "qual_component_run_debug": 50,
}

def get_row_limit(tool_name: str) -> int:
    """Return max rows for array-like mock responses for this tool. Default 50."""
    return DEFAULT_ROW_LIMITS.get(tool_name, 50)


def get_mock_seed(tool_name: str, study_id: str | None = None) -> int | None:
    """Return a deterministic seed for mock generation (same inputs -> same mock). None = random."""
    if not study_id:
        return None
    return hash((tool_name, study_id)) % (2**31)
