# Smoke Test: Manual Verification After Changes

Use this checklist after making changes to the pipeline, backend, or frontend to confirm existing behavior still works.

## Prerequisites

- Python 3.10+ with project dependencies installed (`pip install -r backend/requirements.txt` and project deps).
- Node 18+ for frontend (`cd frontend && npm install`).
- Optional: Set `BYPASS_AUTH_DEV=1` and leave `GOOGLE_CLIENT_ID` unset to use bypass login.

## Steps

1. **Start the backend**
   - From project root: `python run_backend.py` (or `uvicorn backend.main:app --port 8000`).
   - Confirm it starts without errors and listens on port 8000.

2. **Start the frontend**
   - `cd frontend && npm run dev`.
   - Open http://localhost:5173 in a browser.

3. **Auth**
   - You should see the login page. If bypass is enabled: click "Bypass login (development)" and land on the dashboard. Otherwise sign in with Google.

4. **Dashboard**
   - Dashboard loads: status (e.g. Idle), Start/Stop buttons, Settings section, Progress area, Activity stream, Error log.

5. **Settings**
   - Open Settings; confirm tabs/sections (API & credentials, Qualtrics, Grid, Box, Processing, Schedule, Fraud detection).
   - Change a non-secret value (e.g. Qualtrics Survey ID), click Save (with or without "Save to file"). Confirm no error and that the value appears after refresh.

6. **Run pipeline (optional, requires valid tokens)**
   - If Qualtrics and Grid tokens are configured: click Start. Confirm status becomes "Running", progress/activity update, then "Completed" or "Failed"/"Stopped".
   - Click Stop during a run; confirm status moves to "Stopped" and activity shows stop message.

7. **Box / Grid browse (optional)**
   - In Settings, Box tab: click "Browse Box folders". If config is valid, a modal lists folders.
   - Grid tab: click "Browse Grid studies". If token is valid, studies list.

8. **Help & Support**
   - Open Help & Support; confirm content and tabs load.

9. **Sign out**
   - Use header user menu → Sign out. Confirm redirect to login page.

## Backend-only (no frontend)

- `GET /api/status` returns JSON with `runId`, `status`, `currentStep`, `progressPercent`, `message` (requires auth session).
- `GET /auth/me` returns user when session cookie is valid; 401 when not.

## Pipeline standalone (no UI)

- From project root with env set (e.g. `QUALTRICS_API_TOKEN`, `GRID_API_TOKEN`, survey/box IDs): `python backend/qualtrics_box_task.py`.
- Pipeline runs to completion or failure; no HTTP.

## When to run

- After refactors to backend state, routers, or pipeline.
- Before releasing or merging large changes.
- When adding or changing auth, config, or run flow.
