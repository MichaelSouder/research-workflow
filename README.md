# Research Workflow

Pipeline that exports Qualtrics survey responses, optionally runs fraud detection, syncs to Grid (subjects/events), and uploads media to Box. Includes a React + FastAPI UI to run the pipeline, view progress and activity, and manage config (tokens, Box folder, Grid study, fraud options).

## What it does

- **Pipeline** (`backend/qualtrics_box_task.py`): Qualtrics export → normalize → optional fraud filtering → Grid (subjects, events, event details) → Box (create folder, upload videos).
- **Backend** (FastAPI): Runs the pipeline in a subprocess, exposes status/activity/errors, config (env vars), start/stop, and Box/Grid browse endpoints.
- **Frontend** (React + Vite + Tailwind): Dashboard with progress, activity stream, error log, Settings (env + Box folder + Grid study), and Fraud detection options.

## Quick start

### Pipeline (standalone)

From project root, set required env vars (or use the UI to save config), then:

```bash
pip install -r requirements.txt
python backend/qualtrics_box_task.py
```

Required env: `QUALTRICS_API_TOKEN`, `GRID_API_TOKEN`. Other settings can be configured in the UI (per study) or passed via environment variables for standalone runs.

**Distribution commands (no full pipeline):** To run only mailing-list/distribution actions (check IDs, list contacts, send or delete distributions, export survey as CSV), use `--cmd`:

```bash
python backend/qualtrics_box_task.py --cmd check          # validate survey, mailing list, message IDs
python backend/qualtrics_box_task.py --cmd list           # list contacts (with embedded data)
python backend/qualtrics_box_task.py --cmd slist          # short contact list
python backend/qualtrics_box_task.py --cmd send           # send distributions (SMS/email)
python backend/qualtrics_box_task.py --cmd delete        # delete unsent distributions
python backend/qualtrics_box_task.py --cmd delete --index 0   # delete unsent for contact at index 0
python backend/qualtrics_box_task.py --cmd export --format csv   # export survey responses as CSV
```

Set distribution-related env vars (e.g. `QUALTRICS_DIRECTORY_ID`, `QUALTRICS_MAILING_LIST_ID`, `QUALTRICS_LIBRARY_ID`, message IDs) when using these commands. Omitting `--cmd` runs the full pipeline as above.

### Backend + Frontend (UI)

**One command (recommended):** From project root:

```bash
./start.sh
```

Then open **http://localhost:48722** in Safari (or Chrome). If Safari says "can't connect to server", the frontend isn’t running—run `./start.sh` first and wait until you see "Open http://localhost:48722".

**Or start each manually:**

1. **Backend:** From project root: `pip install -r backend/requirements.txt` then `python run_backend.py`
2. **Frontend:** In a second terminal: `cd frontend && npm install && npm run dev`
3. Open **http://localhost:48722** in Safari (Vite proxies `/api` to the backend).

## Layout

- `backend/pipeline/` – Qualtrics, Grid, Box clients; config; normalize; run orchestration.
- `backend/qualtrics_box_task.py` – Thin entrypoint that calls `backend.pipeline.run.main()`.
- `backend/pipeline/fraud_detection.py` – Fraud/integrity checks (speed, duplicate IP, straightlining, incomplete).
- `backend/` – FastAPI app, routers (status, run, config, box, grid), services (state, config, pipeline runner).
- `frontend/` – React app; `src/components/`, `src/api.js`, `src/constants.js`.
- `plans/` – Future plans ([plans/README.md](plans/README.md)).
- `tests/` – Pytest tests for normalize, fraud_detection, backend config.

## Tests

From project root:

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Docker Compose

Run the full stack (frontend + backend + MariaDB):

```bash
docker compose up --build
```

Then open `http://localhost:48722`.

Notes:
- Custom components are persisted on host at `backend/custom_components` and mounted into backend container.
- Backend API is exposed at `http://localhost:48721` (override `BACKEND_PUBLISH` in `.env` to change the bind address, e.g. loopback on a server).
- Default compose uses `BYPASS_AUTH_DEV=1`; configure Google OAuth env vars in `docker-compose.yml` for real auth.

### Production deployment

For TLS, OAuth, and remote hosts (e.g. `lnpiapp.med.umn.edu`), use `docker-compose.prod.yml` and `.env.production` — see [deploy/README.md](deploy/README.md) and `.env.production.example`.

## Config

- **Pipeline:** Reads from `os.environ` (no default tokens; fail-fast if missing when run standalone).
- **UI/Backend:** All app config is stored in the database (per-study: `study_config`, Box JWT in `study_box_config`, processed response IDs in `processed_response_ids`). No `ui_config.json` or config files are used in normal operation. Box config can be uploaded or pasted in the UI (Connections → Box). When you click Start, the backend injects config (and temp files for Box credentials and processed IDs) into the pipeline subprocess.
- **Custom components:** Stored in `backend/custom_components/` by default (override with `CUSTOM_COMPONENTS_DIR`).
- **Local Box file fallback (optional):** If you still run standalone scripts with a file path, use `box.config.example.json` as a template and keep your real `box.config.json` untracked.

## Docker persistence for custom components

If backend runs in Docker, mount a host volume to persist the custom component directory:

```yaml
services:
  backend:
    environment:
      CUSTOM_COMPONENTS_DIR: /app/backend/custom_components
    volumes:
      - ./backend/custom_components:/app/backend/custom_components
```
