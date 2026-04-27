#!/usr/bin/env bash
# Run the Qualtrics automation MCP server from the project root so Python finds the ai package.
# Use this as the MCP "command" if your client doesn't set cwd correctly (e.g. "No module named ai").

cd "$(dirname "$0")"
exec .venv/bin/python -m ai
