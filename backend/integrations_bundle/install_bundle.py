#!/usr/bin/env python3
"""
Run once after unzipping the Claude MCP bundle.

Writes claude_desktop_config.fragment.json with absolute paths so Claude Desktop
does not rely on cwd or a guessed location (e.g. ~/Downloads).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PLACEHOLDER = "__BUNDLE_DIR__"


def main() -> int:
    root = Path(__file__).resolve().parent
    template_path = root / "claude_desktop_config.fragment.template.json"
    if not template_path.is_file():
        print(f"Missing {template_path.name} in {root}", file=sys.stderr)
        return 1

    data = json.loads(template_path.read_text(encoding="utf-8"))
    root_s = str(root)
    server = data.get("mcpServers", {}).get("research-workflow")
    if not isinstance(server, dict):
        print("Invalid template: missing mcpServers.research-workflow", file=sys.stderr)
        return 1

    cwd = server.get("cwd")
    if isinstance(cwd, str) and _PLACEHOLDER in cwd:
        server["cwd"] = cwd.replace(_PLACEHOLDER, root_s)

    args = server.get("args")
    if isinstance(args, list):
        server["args"] = [a.replace(_PLACEHOLDER, root_s) if isinstance(a, str) else a for a in args]

    out = root / "claude_desktop_config.fragment.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print()
    print("Next: merge the `mcpServers` block from that file into Claude Desktop config, then restart Claude.")
    print("  macOS: ~/Library/Application Support/Claude/claude_desktop_config.json")
    print()
    print("If `python3` is not the interpreter where you ran `pip install -r requirements-bridge.txt`,")
    print("edit `command` in the fragment to the full path (run: which python3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
