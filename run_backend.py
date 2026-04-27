#!/usr/bin/env python3
"""
Start the UI backend from the project root.
Run from anywhere:  python run_backend.py
Or from project root:  python run_backend.py
"""
import os
import sys

# Ensure project root is on path and is cwd
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv

    # override=True: project .env wins over stray shell exports (common cause of
    # "correct .env but wrong OAuth client / redirect_uri" when GOOGLE_* was set in ~/.zshrc).
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)
except ImportError:
    pass

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", "48721"))
    # Disable reload when NO_RELOAD=1 so the process stays up in background (e.g. in Cursor)
    use_reload = os.environ.get("NO_RELOAD", "").lower() not in ("1", "true", "yes")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=use_reload,
    )
