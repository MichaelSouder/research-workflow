# Frontend refactor & platform admin plan

This document captures a structured plan for refactoring the Research Workflow frontend toward a CRM-style admin experience (inspired by [Shadcn UI Kit — CRM dashboard](https://shadcnuikit.com/dashboard/crm)), and for adding first-class management of **users**, **privileges**, **MCP/tool API keys** (JSON/Bearer tokens), and **admin-visible API audit logs**.

Use this as a review checklist; adjust phases to match team capacity.

---

## Current state (baseline)

| Area | Notes |
|------|--------|
| Stack | React + Vite, Tailwind, shadcn-style UI (`Card`, `Table`, etc.), React Router, session cookies via `credentials: 'include'`. |
| Layout | `AppLayout` → `AppSidebar` + `AppTopBar` + `Outlet`; main nav: Studies, Platform (superuser), Help. |
| API client | `frontend/src/api.js` — single large module; platform admin uses `getPlatformUsers`, `patchPlatformUserSuperuser`. |
| Platform admin | `frontend/src/components/PlatformLayout.jsx` + pages under `/platform/*` (dashboard, users, API keys, logs). |
| Backend admin | `backend/routers/admin.py` — `GET/PATCH /api/admin/users` (superuser-only). |
| Tool / MCP HTTP API | `backend/routers/tool_api.py` — `POST /v1/tools/invoke`; auth via `Authorization: Bearer` or `X-API-Key`; keys from env `MCP_API_KEY` / `MCP_API_KEYS`. All valid keys resolve to the same MCP bot user (`ai/auth.py`). Logging: single `logger.info` line per invocation — **not queryable from the UI**. |
| Study roles | `frontend/src/lib/roles.js` — `admin` / `editor` (staff) semantics; study membership managed per study. |

---

## Goals

1. **Clearer information architecture** — One consistent shell; separate **research workflows** (studies, pipelines, distribution) from **platform administration** (users, API keys, audit).
2. **CRM-inspired UX** — Dashboard landing for superusers (stat cards, dense tables, filters, optional command palette), without requiring purchase of a commercial template (use as **visual reference** only unless you license the kit).
3. **Manageable API tokens** — Create, label, rotate, revoke keys; optional **scopes** / study allowlists; never store raw secrets after first display (hash at rest).
4. **Observable tool API usage** — Superusers can **search and filter** invocations by time, key, tool name, study, status; sensible defaults for **PII** (metadata-first logging).

---

## Non-goals (initially)

- Pixel-perfect clone of the external CRM template.
- Full arbitrary RBAC for every tool on day one — start with **key CRUD + audit + tool allowlist** (or coarse groups), then tighten.
- Storing full request/response bodies in logs by default (high PII/secret risk).

---

## Information architecture (routes)

| Route | Purpose | Auth |
|-------|---------|------|
| `/studies`, `/studies/:id`, … | Existing study workflows | Logged-in users |
| `/platform` | **Admin dashboard** — KPIs: user count, active keys, invocations (24h/7d), error rate | Superuser |
| `/platform/users` | User directory (search, table) | Superuser |
| `/platform/users/:id` | User detail: profile summary, study memberships & roles | Superuser |
| `/platform/api-keys` | API keys: create, rotate, revoke, scopes, masked display | Superuser |
| `/platform/api-logs` | Tool API audit log viewer (filters, pagination, row detail) | Superuser |

**Implementation note:** Introduce a **`PlatformLayout`** wrapper (secondary nav or tabs: Overview · Users · API keys · Logs) so admin feels like one app. Keep existing `/platform/users` URL or add redirects if routes move.

---

## Frontend refactor (phased)

### Phase A — Shell and design system

- [ ] Add **`PlatformLayout`** with shared header pattern: title, description, primary actions (e.g. “Create API key”), optional date range on dashboard.
- [ ] Define **`AdminPageFrame`** / **`DashboardSection`** primitives: stat grid → main card/table (matches CRM-style hierarchy).
- [ ] Align **spacing, typography, and card headers** across new platform pages; reuse `PageHeader`, `Breadcrumb`, `Card`, `Table`.
- [ ] Optional: **Command palette** (`cmdk`) for superusers — quick jump to Users, API keys, Logs.

### Phase B — Consolidate repeated patterns

- [ ] Standardize **loading** (skeleton), **empty**, and **error** states for admin tables.
- [ ] Reduce duplicate `min-h-full bg-muted/30` wrappers via layout components (avoid over-abstracting).

### Phase C — API module organization (when painful)

- [ ] Split `api.js` into domain files, e.g. `api/platform.js`, `api/studies.js`, or add a thin `fetchJson` helper with shared error handling.

### Phase D — Study app (optional, later)

- [ ] After platform shell is stable, migrate **one** study page as a template for visual parity; avoid big-bang rewrite of all study screens.

### Accessibility & responsive

- [ ] Tables: horizontal scroll + sticky first column where needed; keyboard-friendly filters.

---

## Backend: API keys & privileges (required for “great” token UX)

### Current limitation

Keys live only in **environment variables**; there is no per-key identity, rotation in UI, or linkage to a human user.

### Target model

| Concept | Description |
|---------|-------------|
| **Stored key record** | `id`, `name`, `created_at`, `revoked_at`, `last_used_at`, **`key_prefix`** (for display), **`key_hash`** (verify only; use a strong hash), optional **`owner_user_id`**, optional **`expires_at`**. |
| **Issuance** | On create, return **full secret once**; thereafter show only prefix + metadata. |
| **Verification** | `get_tool_api_user` resolves Bearer/API key → validate against **hashed** store (and optionally legacy env keys during migration). |
| **Scopes (phased)** | **Phase 1:** allowlist of **tool names** or coarse groups (`read`, `study_write`, `distribution`, `dangerous`). **Phase 2:** optional **study_id allowlist** for tools that accept `study_id`. |
| **Migration** | Continue honoring `MCP_API_KEY` / `MCP_API_KEYS` as **bootstrap** keys until DB keys are primary; document deprecation. |

### Superuser HTTP API (illustrative)

- `GET/POST /api/admin/api-keys` — list, create  
- `PATCH/DELETE /api/admin/api-keys/{id}` — rename, revoke, rotate  
- (Optional) attach scopes in request/response bodies as structured JSON  

*Exact paths should match existing `/api/admin/*` conventions in `backend/routers/admin.py` or a dedicated router.*

---

## Backend: audit log for tool API (required for admin log viewer)

### Current limitation

`invoke_tool` logs via `logger.info` only — not searchable from the app.

### Target: structured events

Store per invocation (minimum viable):

| Field | Notes |
|-------|--------|
| `timestamp` | UTC |
| `api_key_id` | Or `null` for legacy env key if distinguishable |
| `tool` | Tool name |
| `study_id` | From arguments when present |
| `status` | Success / client error / server error |
| `duration_ms` | |
| `error_detail` | Truncated, no secrets |
| **Not by default** | Full `arguments` / response bodies — PII and secret risk |

### Superuser HTTP API (illustrative)

- `GET /api/admin/tool-invocations?from=&to=&key_id=&tool=&study_id=&cursor=`  
- Pagination/cursor for large datasets  

### Operations

- [ ] Define **retention** (e.g. 30–90 days) and optional archival/export for compliance.

---

## UI feature checklist

### Users & privileges

- [ ] **User list** — Search, sort, link to detail.  
- [ ] **User detail** — Study memberships and roles (reuse/extend existing study user APIs where possible).  
- [ ] **Superuser toggle** — Keep existing behavior; ensure it lives under new platform layout.

### API keys

- [ ] **List** — Name, prefix, owner, created, last used, status.  
- [ ] **Create** — Show secret once + copy button.  
- [ ] **Rotate / revoke** — Confirm destructive actions.  
- [ ] **Scopes** — Checkbox or multi-select by phase (see above).

### API logs

- [ ] **Filters** — Time range, key, tool, study, status.  
- [ ] **Table** — Columns for time, key (prefix/id), tool, study, duration, status.  
- [ ] **Row expand / drawer** — JSON-safe detail for error metadata (still no raw secrets).  
- [ ] **Export** — Optional CSV for admins (respect retention).

---

## Execution order (recommended)

1. **Backend:** Persisted API keys (hash), verification path, audit writes on `POST /v1/tools/invoke`, superuser list endpoints.  
2. **Frontend:** `PlatformLayout` + dashboard + `/platform/api-keys` + `/platform/api-logs`; migrate users page into layout.  
3. **Scopes** — Start with tool allowlist or groups; add study allowlist when needed.  
4. **Polish** — Command palette, retention UI, export.

---

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Scope creep on RBAC | Ship keys + audit + coarse scopes first. |
| Log volume / DB size | Retention policy, indexes on `(timestamp, api_key_id)`, pagination. |
| Secret leakage in logs | Never log Bearer tokens; redact known secret fields in optional debug modes. |
| Template licensing | Use CRM link as **design reference**; open-source shadcn components for implementation. |

---

## Open decisions (fill in during review)

- [ ] **Storage:** Same `Datastore` abstraction vs new table module — align with deployment/backup.  
- [ ] **Key ownership:** Must every key tie to a `User`, or allow service accounts without OAuth users?  
- [ ] **Default scopes** for new keys: deny-all vs read-only preset?  
- [ ] **Audit payload policy:** Are truncated argument snippets ever allowed under a feature flag?

---

## Reference files (repo)

- Frontend entry & routes: `frontend/src/App.jsx`  
- Platform UI: `frontend/src/components/PlatformLayout.jsx`, `frontend/src/pages/Platform*Page.jsx`  
- API client: `frontend/src/api.js`  
- Tool API: `backend/routers/tool_api.py`  
- Admin API: `backend/routers/admin.py`  
- MCP user resolution: `ai/auth.py`  
- Study roles (frontend): `frontend/src/lib/roles.js`  

---

*Last updated: 2026-04-06*
