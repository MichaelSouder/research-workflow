"""Registry of tool name -> real implementation. Used by the proxy to run the real tool and then mock the response."""

from typing import Any, Callable

from ai.tools import box_grid, components, config, distribution, pipelines, status, studies

# Map each sensitive (and related) tool name to the function that implements it.
# The proxy calls this function with **kwargs to get the real JSON string response.
INVOKERS: dict[str, Callable[..., str]] = {
    # Studies
    "qual_studies_list": studies.qual_studies_list,
    "qual_study_get": studies.qual_study_get,
    "qual_study_users_list": studies.qual_study_users_list,
    # Pipelines
    "qual_pipelines_list": pipelines.qual_pipelines_list,
    "qual_pipeline_get": pipelines.qual_pipeline_get,
    # Config
    "qual_study_config_get": config.qual_study_config_get,
    "qual_config_get": config.qual_config_get,
    # Status / activity
    "qual_status": status.qual_status,
    "qual_study_status": status.qual_study_status,
    "qual_activity": status.qual_activity,
    "qual_study_activity": status.qual_study_activity,
    "qual_study_errors": status.qual_study_errors,
    # Distribution
    "qual_distribution_contacts": distribution.qual_distribution_contacts,
    "qual_distribution_check": distribution.qual_distribution_check,
    "qual_distribution_status": distribution.qual_distribution_status,
    "qual_distribution_list": distribution.qual_distribution_list,
    "qual_distribution_send_preview": distribution.qual_distribution_send_preview,
    "qual_distribution_export": distribution.qual_distribution_export,
    # Box / Grid
    "qual_box_folders": box_grid.qual_box_folders,
    "qual_grid_studies": box_grid.qual_grid_studies,
    "qual_component_run_debug": components.qual_component_run_debug,
}


def get_invoker(tool_name: str) -> Callable[..., str] | None:
    """Return the real implementation for a tool, or None if not registered."""
    return INVOKERS.get(tool_name)
