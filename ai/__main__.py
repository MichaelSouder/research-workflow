"""
Entrypoint for the MCP server: python -m ai

Initializes backend state, datastore, and MCP user; sets context; then runs the MCP server over stdio.
Ensure the project root is on PYTHONPATH (e.g. run from repo root: uv run python -m ai).
"""

import sys

# Ensure project root is importable (backend, pipeline, ai)
if __name__ == "__main__":
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from backend.datastore import get_datastore
from backend.migration import ensure_default_study
from backend.services import state

from ai.auth import get_mcp_user
from ai.context import set_context
from ai.server import mcp


def main() -> None:
    state.load_config()
    store = get_datastore()
    ensure_default_study(store, state.CONFIG_FILE)
    user = get_mcp_user(store)
    set_context(store, user)
    mcp.run()


if __name__ == "__main__":
    main()
