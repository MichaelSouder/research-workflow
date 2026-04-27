# Architecture: Research Workflow

Summary of pipeline, backend, and frontend.

## Boundaries

| Layer      | Responsibility                                              | Config              | Entry point                          |
|------------|--------------------------------------------------------------|---------------------|--------------------------------------|
| **Pipeline** | Qualtrics → normalize → fraud → Grid → Box; distribution CLI. No HTTP. | Env only            | `backend/qualtrics_box_task.py` → `pipeline.run.main()` or `--cmd` |
| **Backend**  | HTTP API, run state, study config, scheduler, Box/Grid/Distribution. | Datastore (study_config, etc.); env for defaults | `run_backend.py` / uvicorn           |
| **Frontend** | UI only; all data via API.                                  | None (reads backend) | Vite dev server / static build       |

## Pipeline

- **Entry:** `backend/qualtrics_box_task.py` calls `pipeline.run.main()` (full pipeline) or `run_cmd()` when `--cmd` is set (distribution commands).
- **Config:** Environment variables only (injected by backend when started from UI, or by shell when run standalone).
- **Modules:** `pipeline/` (qualtrics_client, qualtrics_distribution, normalize, box_client, grid_client, processed_store, config, run, fraud_detection) under `backend/pipeline/`.
- **No HTTP:** Pipeline does not depend on the backend.

## Backend

- **Framework:** FastAPI.
- **Routers:** auth, studies (config, status, run, users, box, grid, distribution), status, run, config_routes, box, grid.
- **State:** Run state in `backend/services/state.py`; study-scoped config and persistence in datastore (MariaDB or mock).
- **Config:** Study config in datastore (`study_config`, `study_box_config`, processed IDs); backend injects into pipeline subprocess. No `ui_config.json` in normal operation (migration only).

## Frontend

- **Stack:** React, Vite, shadcn/Tailwind.
- **Routes:** `/login`, `/studies`, `/studies/:studyId` (pipelines), `/studies/:studyId/admin`, `/studies/:studyId/distribution`, `/studies/:studyId/pipeline-graph`, `/profile`, `/help`.
- **Data:** All data via API (`api.js`); shared constants in `constants.js`.
- **Auth:** Login (Google OAuth or dev bypass); session cookie; study access by role (viewer, editor, admin).

## Data Flow

1. User configures Qualtrics, Grid, Box, Distribution (per study) in the UI; backend saves to datastore (`study_config`, etc.).
2. User clicks Start (for a study); backend builds env from study config, starts `backend/qualtrics_box_task.py` as a subprocess, updates run state (status, step, progress, activity).
3. Frontend polls study status/activity/errors; displays progress and activity.
4. Box/Grid/Distribution: frontend calls study-scoped endpoints; backend uses study config and returns data.

## Smoke Test

See [docs/smoke-test.md](smoke-test.md) for manual verification steps.
