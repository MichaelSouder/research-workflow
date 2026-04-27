"""
stdio MCP server that forwards each tool call to the Research Workflow HTTP tool API.

Install: pip install mcp httpx
Environment (required):
  RW_BASE_URL — public base URL (e.g. https://app.example.edu), no trailing slash
  RW_API_KEY — plaintext tool API key (Bearer)
  RW_TOOL_NAMES_JSON — JSON array of tool names, e.g. ["qual_studies_list",...]
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

BASE = (os.environ.get("RW_BASE_URL") or "").strip().rstrip("/")
KEY = (os.environ.get("RW_API_KEY") or "").strip()
_raw_tools = (os.environ.get("RW_TOOL_NAMES_JSON") or "").strip()
try:
    TOOL_NAMES = json.loads(_raw_tools) if _raw_tools else []
except json.JSONDecodeError as e:
    raise RuntimeError(f"Invalid RW_TOOL_NAMES_JSON: {e}") from e
if not BASE or not KEY:
    raise RuntimeError("RW_BASE_URL and RW_API_KEY are required.")
if not isinstance(TOOL_NAMES, list) or not all(isinstance(x, str) for x in TOOL_NAMES):
    raise RuntimeError("RW_TOOL_NAMES_JSON must be a JSON array of strings.")
if not TOOL_NAMES:
    raise RuntimeError("RW_TOOL_NAMES_JSON must list at least one tool name.")

server = Server("research-workflow-bridge")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=n,
            description=f"Research Workflow tool `{n}` (forwarded to HTTP API).",
            inputSchema={"type": "object", "additionalProperties": True},
        )
        for n in TOOL_NAMES
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    if name not in TOOL_NAMES:
        return [types.TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    payload = {"tool": name, "arguments": arguments or {}}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{BASE}/v1/tools/invoke",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json=payload,
        )
    return [types.TextContent(type="text", text=r.text)]


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio

    asyncio.run(_run())


if __name__ == "__main__":
    main()
