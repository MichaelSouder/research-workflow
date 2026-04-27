"""
Data proxy: run real tool, infer schema from response, return mock data so real data is never exposed.
Enable with MCP_DATA_PROXY_ENABLED=1.
"""

from __future__ import annotations

import json

from ai.proxy.defaults import (
    SENSITIVE_TOOLS,
    get_mock_seed,
    get_row_limit,
    is_proxy_enabled,
)
from ai.proxy.export_mock import mock_export_file
from ai.proxy.mock_gen import generate_mock
from ai.proxy.registry import get_invoker
from ai.tools.common import tool_error, tool_result


def _preserve_allowed_real_fields(tool_name: str, real_payload: object, mock_payload: object) -> object:
    """
    Keep explicitly allowed real fields while leaving everything else mocked.
    Current policy:
    - qual_box_folders: real payload allowed
    - qual_studies_list: preserve study names
    - qual_study_get: preserve study name
    """
    if tool_name == "qual_box_folders":
        return real_payload
    if not isinstance(real_payload, dict) or not isinstance(mock_payload, dict):
        return mock_payload
    if tool_name == "qual_studies_list":
        real_studies = real_payload.get("studies")
        mock_studies = mock_payload.get("studies")
        if isinstance(real_studies, list) and isinstance(mock_studies, list):
            for i, real_item in enumerate(real_studies):
                if i >= len(mock_studies):
                    break
                if isinstance(real_item, dict) and isinstance(mock_studies[i], dict):
                    if "name" in real_item:
                        mock_studies[i]["name"] = real_item.get("name")
        return mock_payload
    if tool_name == "qual_study_get":
        if "name" in real_payload:
            mock_payload["name"] = real_payload.get("name")
        return mock_payload
    return mock_payload


def invoke_and_mock(tool_name: str, **kwargs: object) -> str:
    """
    Run the real tool, then return a mock response with the same structure.
    Errors from the real tool are passed through unchanged. Real data is never returned.
    """
    invoker = get_invoker(tool_name)
    if not invoker:
        return tool_error("Unknown or unsupported tool for proxy")
    try:
        real_str = invoker(**kwargs)
    except Exception:
        # Never expose raw error details for proxied sensitive tools.
        if tool_name in SENSITIVE_TOOLS:
            return tool_error("Request failed while generating proxied response.")
        return tool_error("Request failed.")
    if tool_name not in SENSITIVE_TOOLS:
        return real_str
    try:
        parsed = json.loads(real_str)
    except json.JSONDecodeError:
        # If sensitive output isn't JSON, do not pass through raw content.
        return tool_error("Request failed while generating proxied response.")
    if isinstance(parsed, dict) and parsed.get("error"):
        err_msg = str(parsed.get("error", ""))
        # Pass through policy errors (confirmation, allowlist) so callers can retry with confirm.
        if (
            "Dangerous operation not confirmed" in err_msg
            or "allowlist" in err_msg.lower()
            or "Data proxy mode" in err_msg
        ):
            return tool_error(err_msg)
        # Other errors may contain sensitive details; return a generic proxy-safe error.
        return tool_error("Request failed while generating proxied response.")
    row_limit = get_row_limit(tool_name)
    seed = get_mock_seed(tool_name, kwargs.get("study_id") if isinstance(kwargs.get("study_id"), str) else None)
    if tool_name == "qual_distribution_export":
        path = parsed.get("path")
        if path and isinstance(path, str):
            try:
                mock_path = mock_export_file(
                    path,
                    parsed.get("format", "json"),
                    study_id=str(kwargs.get("study_id")) if kwargs.get("study_id") else None,
                    row_limit=min(row_limit, 100),
                )
                parsed = {"ok": True, "path": mock_path, "format": parsed.get("format", "json")}
            except Exception as e:
                return tool_error(f"Export mock failed: {e}")
        else:
            mock_payload = generate_mock(parsed, row_limit=row_limit, seed=seed)
            mock_payload = _preserve_allowed_real_fields(tool_name, parsed, mock_payload)
            return tool_result(mock_payload)
    else:
        mock_payload = generate_mock(parsed, row_limit=row_limit, seed=seed)
    mock_payload = _preserve_allowed_real_fields(tool_name, parsed, mock_payload)
    return tool_result(mock_payload)
