# Comparison: qualtrics-automation vs kelvinlim/qualtrics_util

This report compares the functionality of **this project** (qualtrics-automation) with the open-source **kelvinlim/qualtrics_util** ([GitHub](https://github.com/kelvinlim/qualtrics_util/tree/main)).

**Note:** Distribution and mailing list features from qualtrics_util have been ported into this app (study-scoped Distribution page, CLI `--cmd`, backend API). This doc remains as a capability reference.

---

## Executive summary

| Aspect | kelvinlim/qualtrics_util | This project (qualtrics-automation) |
|--------|---------------------------|-------------------------------------|
| **Primary focus** | Mailing lists, distributions (SMS/email), scheduling | Survey export → downstream pipeline (Grid, Box, fraud) |
| **Interface** | CLI only | CLI + React + FastAPI UI |
| **Qualtrics usage** | Mailing lists, contacts, distributions, send/delete | Survey response export, uploaded media download |
| **Overlap** | Survey export (JSON/CSV) | Survey export (JSON) |
| **Unique to util** | Send/delete distributions, list contacts, time slots, crontab | Fraud detection, Grid subjects/events, Box upload, UI |

The two projects target different workflows: **qualtrics_util** is for managing *outbound* survey distribution (SMS/email, scheduling, contact lists). **This project** is for *inbound* data: exporting responses, validating them, and pushing to Grid + Box.

---

## 1. Functionality comparison

### 1.1 kelvinlim/qualtrics_util — feature list

- **Config**
  - `.env` for `QUALTRICS_APITOKEN`
  - YAML config (`config_qualtrics.yaml`) for survey, mailing list, library, message IDs, embedded data
  - `--config` to specify another config file

- **Commands (CLI)**
  - **check** — Validate survey ID, mailing list ID, message ID; get contact list and distributions
  - **list** — Long listing of mailing list contacts (with embedded data)
  - **slist** — Short listing (index, scheduled count, method, date, name, email, phone, etc.)
  - **send** — Send distributions for contacts where `SurveysSchedule=0` and `UseSMS=1` (or email)
  - **delete** — Delete unsent distributions for contacts with `DeleteUnsent=1` (by index)
  - **update** — Update embedded data for all contacts in the mailing list
  - **export** — Export survey responses to JSON (default) or CSV

- **Distribution & contacts**
  - SMS and email distributions (separate message IDs, `ContactMethod`)
  - Get/create/update contacts and embedded data
  - Delete SMS or email distributions (unsent only)
  - Time slots for scheduling (e.g. `[800,900], [1200,1300]`), timezone (IANA), expiry minutes
  - Crontab-friendly usage for send/delete

- **Export**
  - Survey response export (JSON or CSV), progress polling, optional pandas DataFrame return

- **Packaging**
  - PyInstaller single-file executable, Makefile for build/deploy

**APIs used (conceptually):** Directories, mailing lists, contacts, distributions (email + SMS), survey response export, library messages.

---

### 1.2 This project (qualtrics-automation) — feature list

- **Config**
  - Env vars (e.g. `QUALTRICS_API_TOKEN`, `GRID_API_TOKEN`, `BOX_ROOT_FOLDER_ID`, `FRAUD_*`)
  - Optional `ui_config.json` (or equivalent) for UI-saved settings; backend injects into pipeline subprocess

- **Pipeline (CLI: `backend/qualtrics_box_task.py`)**
  - **Qualtrics:** Survey response export (JSON only), parse responses, download uploaded media (e.g. videos) by file ID
  - **Normalize:** Normalize response data (names, completion, field mapping)
  - **Duplicate handling:** Skip already-processed response IDs (e.g. `processed_response_ids.json`)
  - **Fraud detection (optional):** Speed, duplicate IP, straightlining, incomplete (configurable via env)
  - **Grid:** Subject lookup/create, subject-study, events, event details (e.g. “QualtricsVideoBoxArchive”)
  - **Box:** Create folder per subject/event, upload media (e.g. two videos per response)

- **Backend (FastAPI)**
  - Status, run pipeline (start/stop), config (read/update), Box folder browse, Grid study browse

- **Frontend (React + Vite)**
  - Dashboard: progress, activity stream, error log
  - Settings: env/tokens, Box folder, Grid study, fraud options
  - Browse modals for Box and Grid

**APIs used:** Qualtrics survey export + uploaded-files download; Grid (custom LNP API: subjects, events, event details); Box (folders, upload).

---

## 2. Side-by-side capability matrix

| Capability | kelvinlim/qualtrics_util | This project |
|------------|--------------------------|--------------|
| Qualtrics API token / config | ✅ .env + YAML | ✅ Env (and UI config) |
| Survey response export | ✅ JSON, CSV | ✅ JSON only |
| Export progress / polling | ✅ Yes | ✅ Yes |
| Mailing list / contacts | ✅ List, update, embedded data | ❌ No |
| Send distributions (SMS/email) | ✅ Yes | ❌ No |
| Delete unsent distributions | ✅ Yes (SMS + email) | ❌ No |
| Time slots / scheduling | ✅ Yes (e.g. time ranges) | ❌ No |
| Timezone validation | ✅ IANA in config | ❌ N/A (no scheduling) |
| Download survey uploaded files | ❌ No | ✅ Yes (e.g. videos) |
| Normalize / map response data | ❌ No | ✅ Yes |
| Fraud / integrity checks | ❌ No | ✅ Yes (speed, IP, straightline, incomplete) |
| Duplicate response skip | ❌ No | ✅ Yes (processed store) |
| Grid (subjects, events, details) | ❌ No | ✅ Yes |
| Box (folders, upload) | ❌ No | ✅ Yes |
| Web UI | ❌ No | ✅ React + FastAPI |
| CLI | ✅ Yes | ✅ Yes (pipeline entrypoint) |
| Crontab / headless | ✅ Designed for it | ✅ Pipeline can be cron-run |
| Single executable (e.g. PyInstaller) | ✅ Yes | ❌ No |

---

## 3. Qualtrics API surface

- **qualtrics_util**
  - Directories, mailing lists, contacts (CRUD, embedded data)
  - Distributions: email and SMS (list, create, delete)
  - Library messages
  - Survey response export (v3 export-responses)

- **This project**
  - Survey response export (v3 export-responses)
  - Survey response uploaded-files download (v3 surveys/…/responses/…/uploaded-files/…)

So: **qualtrics_util** covers distribution and contact management; **this project** uses only export and media download.

---

## 4. Gaps and possible reuse

### 4.1 In this project (not in qualtrics_util)

- Fraud detection, Grid, Box, UI — all specific to this workflow; no direct equivalent in qualtrics_util.

### 4.2 In qualtrics_util (not in this project)

- **Mailing list and contact management** — list/update contacts, embedded data.
- **Distributions** — send SMS/email invites, delete unsent.
- **Scheduling** — time slots, timezone, expiry; crontab-oriented send/delete.
- **Export format** — CSV in addition to JSON.
- **Packaging** — PyInstaller + Makefile for a single binary.

If you ever need to:
- Send or schedule survey invitations (SMS/email),
- Manage mailing list contacts or embedded data,
- Or delete unsent distributions from this codebase,

you could either:
- Call qualtrics_util as a subprocess (e.g. `qualtrics_util --cmd send`), or
- Port the relevant parts of [qualtrics_util](https://github.com/kelvinlim/qualtrics_util) (contact/distribution APIs) into this repo and keep a single stack.

### 4.3 Shared ground

- **Survey response export:** Both use the same Qualtrics export API. Our pipeline uses JSON only; util adds CSV and optional DataFrame. Logic is similar (progress ID → file ID → download → unzip).

---

## 5. Summary

- **kelvinlim/qualtrics_util** is a **distribution and contact-list** tool: send/delete invitations (SMS/email), manage contacts and embedded data, optional survey export (JSON/CSV), with CLI and crontab in mind.
- **This project** is an **export-and-downstream** pipeline: export responses, optionally run fraud checks, push to Grid and Box, with a React + FastAPI UI.

There is **no functional overlap** beyond “export survey responses”; the rest is complementary. Adopting or referencing qualtrics_util is most relevant if you add distribution, scheduling, or mailing-list management to this project.

---

*Report generated for comparison with [kelvinlim/qualtrics_util](https://github.com/kelvinlim/qualtrics_util/tree/main).*
