"""
Entry point for Claude Desktop MCP: always run the bridge from this directory.

Claude may start the server with cwd set to ~ or elsewhere, so we chdir to the
folder that contains bridge_stdio.py before executing it.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
os.chdir(_root)
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
runpy.run_path(str(_root / "bridge_stdio.py"), run_name="__main__")
