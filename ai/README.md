# Research Workflow MCP Server

MCP (Model Context Protocol) server that exposes Research Workflow app functionality to LLMs (Cursor, Claude Desktop, ChatGPT, Gemini). Read-only and dangerous tools are both available; dangerous operations require `confirm_dangerous_operation: true`.

## Run the server

From the **repository root** (so `backend` and `pipeline` are importable):

```bash
uv run python -m ai
```

Or with system Python (with dependencies and repo root on `PYTHONPATH`):

```bash
python -m ai
```

The server uses **stdio** transport: it reads JSON-RPC from stdin and writes responses to stdout. No HTTP port.

## Cursor

1. Open Cursor Settings → MCP (or edit `.cursor/mcp.json` in the project).
2. Add a server entry. Example (adjust path if needed):

```json
{
  "mcpServers": {
    "research-workflow": {
      "command": "uv",
      "args": ["run", "python", "-m", "ai"],
      "cwd": "/path/to/research-workflow"
    }
  }
}
```

Or if you run from the project root and `uv` is on your PATH:

```json
{
  "mcpServers": {
    "research-workflow": {
      "command": "uv",
      "args": ["run", "python", "-m", "ai"]
    }
  }
}
```

3. Restart Cursor. The tools (e.g. `qual_studies_list`, `qual_study_get`) will be available to the AI.

## Claude Desktop

Edit Claude’s MCP config (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS) and add:

```json
{
  "mcpServers": {
    "research-workflow": {
      "command": "uv",
      "args": ["run", "python", "-m", "ai"],
      "cwd": "/path/to/research-workflow"
    }
  }
}
```

Restart Claude Desktop.

## In-process mode

The server uses the same datastore and config as the main app. It does **not** need the FastAPI backend to be running for read-only tools (studies, pipelines, config, status, distribution preview, etc.). Tools that call Qualtrics/Grid/Box APIs (e.g. distribution contacts, Box folders, Grid studies) still need the corresponding tokens and config in the datastore (e.g. from the app’s Settings).

- **MCP user:** A dedicated user `mcp-bot@local` is created and given admin on all studies so the LLM can access every study the app knows about.

## Tools (read-only)

| Tool | Description |
|------|-------------|
| `qual_studies_list` | List studies the user has access to, with role |
| `qual_study_get` | Get one study by id |
| `qual_study_users_list` | List users and roles for a study (admin) |
| `qual_pipelines_list` | List pipelines for a study |
| `qual_pipeline_get` | Get pipeline definition (nodes, edges) |
| `qual_study_config_get` | Get study config (secrets masked by default) |
| `qual_config_get` | Legacy single-study config get (errors when multiple studies) |
| `qual_status` | Run status (optional study_id) |
| `qual_study_status` | Run status for a study |
| `qual_activity` | Activity log (optional study_id) |
| `qual_study_activity` | Activity log for a study |
| `qual_study_errors` | Errors/warnings for a study |
| `qual_distribution_contacts` | Mailing list contacts |
| `qual_distribution_check` | Validate survey/mailing list/message IDs |
| `qual_distribution_status` | Send in progress and last result |
| `qual_distribution_list` | List distributions |
| `qual_distribution_send_preview` | Preview who would receive a send |
| `qual_distribution_export` | Export survey responses (path) |
| `qual_box_folders` | List Box folders (optional study_id) |
| `qual_study_box_config_status` | Whether Box config is set |
| `qual_grid_studies` | List Grid studies (optional study_id) |
| `qual_components_list` | List all pipeline components (built-in + custom) |
| `qual_component_get` | Get full manifest for a component by id |
| `qual_component_run_debug` | Run custom component code in sandbox with sample inputs (no pipeline run) |

**Pipeline component tools (dangerous):** `qual_component_create`, `qual_component_update`, `qual_component_delete` — create/update/delete custom pipeline components. Require `confirm_dangerous_operation: true`.

**Resources** (read-only context): `study://default/overview`, `study://{study_id}/summary`, `study://{study_id}/pipeline/{pipeline_id}`, **`spec://pipeline/components`** (pipeline component architecture, execution contract, sandbox API).

**Dangerous tools** (study/pipeline create/update/delete, config set, run start/stop, distribution send/delete_unsent/contact patch, Box config set, study users set/add) require `confirm_dangerous_operation: true`. Optional env `MCP_ALLOWED_DANGEROUS_TOOLS` (comma-separated) restricts which dangerous tools are allowed.

**Secrets:** Config tools mask secrets unless the caller passes `reveal_secrets=true` and the server has `MCP_REVEAL_SECRETS=1` set. Do not enable in shared environments.

## HTTP Tool API (ChatGPT / Gemini)

When the **FastAPI backend** is running, the same tools are available over HTTP for Custom GPT Actions and Gemini:

- **POST /v1/tools/invoke** — Body: `{ "tool": "qual_studies_list", "arguments": {} }`. Auth: `Authorization: Bearer <key>` or `X-API-Key: <key>`.
- **GET /v1/openapi.json** — OpenAPI 3.0 spec for the invoke endpoint.

Set **MCP_API_KEY** or **MCP_API_KEYS** (comma-separated) in the backend environment. Only requests with a valid key are accepted. The backend logs each tool call (tool name, study_id when present, user) for audit. For **Gemini**, see `ai/gemini_tools.json` for a sample of function declarations you can paste into Google AI Studio or Vertex AI (then have your app call `POST /v1/tools/invoke` with the same tool name and arguments).

## Data proxy (mock sensitive data)

When **MCP_DATA_PROXY_ENABLED=1** (or `true`/`yes`), the server replaces real data with **mock data** for all sensitive read tools. The proxy runs the real query to learn schema and value ranges, then returns only synthetic data with the same structure. Use this so users can develop pipelines and code against sample data without ever seeing production data.

- **Enabled:** Set `MCP_DATA_PROXY_ENABLED=1` in the environment before starting the MCP server.
- **Behavior:** Tools such as `qual_studies_list`, `qual_study_get`, `qual_study_users_list`, `qual_distribution_contacts`, `qual_distribution_export`, `qual_pipeline_get`, `qual_study_activity`, `qual_study_errors`, config get, distribution list/preview/check/status, Box folders, Grid studies, and status/activity return mock responses. Errors (e.g. "Study not found") are still returned as-is.
- **Export:** For `qual_distribution_export`, the real export runs to a temp file, schema is inferred, a mock file is written with the same structure, the real file is removed, and the tool returns the path to the mock file.
- **Determinism:** Mock data is seeded by tool name and `study_id` when present so the same request yields the same sample for a session.
- **Row limits:** Mock arrays are capped (e.g. 50 contacts, 30 activity entries); see `ai/proxy/defaults.py` for per-tool limits.

## Config

- **Data:** Uses the same datastore as the app (`DATASTORE=memory` or `DATASTORE=mariadb` with `DATABASE_URL`). No separate config file for the MCP server in in-process mode.
- **Secrets:** Config tools mask secrets unless `reveal_secrets=true` is passed and **MCP_REVEAL_SECRETS=1** is set on the server. Do not enable in shared environments.
