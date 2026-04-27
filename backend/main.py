"""
FastAPI backend for Research Workflow UI.
Runs qualtrics_box_task in a subprocess, exposes status, start/stop, config, Box/Grid browse.
Auth: Google OAuth; sessions in datastore (mock or MariaDB).
"""

from pathlib import Path

# Load project-root .env before any code reads os.environ (OAuth, datastore, CORS, etc.).
# Works with: python run_backend.py, uvicorn backend.main:app, and reload workers.
_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env", override=True)
except ImportError:
    pass

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.datastore import get_datastore
from backend.migration import ensure_default_study
from backend.routers import admin, auth, box, config_routes, distribution, grid, integrations, run, status, studies, tool_api
from backend.services import scheduler as scheduler_service
from backend.services import state


def _warm_pipeline_import():
    """Run in background so lifespan yields quickly and /api/status responds immediately."""
    try:
        state.get_script_default("QUALTRICS_API_TOKEN")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.load_config()
    if os.environ.get("GOOGLE_CLIENT_ID"):
        from backend.routers.auth import describe_oauth_redirect_uri

        print(
            "[research-workflow] Google OAuth redirect_uri (register this in Cloud Console): "
            + describe_oauth_redirect_uri(),
            flush=True,
        )
    app.state.datastore = get_datastore()
    ensure_default_study(app.state.datastore, state.CONFIG_FILE)
    # Start pre-warm in background so server accepts requests right away (avoids stuck loading)
    t = threading.Thread(target=_warm_pipeline_import, daemon=True)
    t.start()
    scheduler_service.start_scheduler(app)
    yield
    scheduler_service.shutdown_scheduler()


app = FastAPI(title="Research Workflow API", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-in-production"),
)
_cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:48722,http://127.0.0.1:48722,http://localhost:15421,http://127.0.0.1:15421,"
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(integrations.router)
app.include_router(admin.router)
app.include_router(studies.router)
app.include_router(distribution.router)
app.include_router(status.router)
app.include_router(run.router)
app.include_router(config_routes.router)
app.include_router(box.router)
app.include_router(grid.router)
app.include_router(tool_api.router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BACKEND_PORT", "48721"))
    uvicorn.run(app, host="0.0.0.0", port=port)
