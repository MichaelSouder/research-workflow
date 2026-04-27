# Design: Reusable Standard Components (Custom Pipeline Nodes)

This doc captures the design for **addable standard components**—like box or qualtrics nodes—with **defined data in/out**, and support for the **MCP AI to create and debug code** inside a node that can be reused.

**See also: [ARCHITECTURE_COMPONENT_FIRST.md](./ARCHITECTURE_COMPONENT_FIRST.md)** — Overhaul so that *every* step (qualtrics, process, grid, box) is a discrete component with the same interface. Custom components then use that same abstraction; the runner is generic.

---

## 1. Current State (Brief)

- **Node types** are fixed in `backend/pipeline_validation.py` (`ALLOWED_NODE_TYPES`: qualtrics, file_import, process, normalize, duplicate_skip, fraud, grid, box, webhook, http_call, stage).
- **Execution** is hardcoded in `pipeline/run.py`: each type maps to a specific function (`_run_qualtrics`, `_run_process`, `_run_grid_box`). Data flows implicitly (e.g. qualtrics → export path + videos_info → process → normalized_records → grid/box).
- **Frontend**: One React Flow node component (`stage`), with `data.pipelineType` carrying the logical type. `componentConfig.js` defines labels and config keys per type; config is study-level key/value, not per-node-type schema.
- **Adding a new built-in type** today requires: (1) add to `ALLOWED_NODE_TYPES`, (2) add runner logic in `pipeline/run.py`, (3) add to `NODE_CATEGORIES` / `NODE_CONFIG` in the frontend.

There is no formal **data contract** (inputs/outputs) per node type and no way to **define or edit node behavior as code** that the AI can work with.

---

## 2. Goal

- **Standard components** that behave like box/qualtrics: first-class node types with a clear **data-in / data-out** contract.
- **Reusable**: once defined, a component can be dropped into any pipeline and wired by edges.
- **Definable by users (or admins)**: component = metadata (id, label, inputs, outputs, config keys) + **code** that runs when the node runs.
- **MCP AI can**:
  - **Create** new components (metadata + code),
  - **Edit** component code (and optionally metadata),
  - **Debug** a component (e.g. run with sample input, see output or errors).

---

## 3. Component Definition Schema (Proposed)

A **component** is a reusable unit with:

| Field | Purpose |
|-------|--------|
| `id` | Unique key (e.g. `enrich_api`, `send_slack`). Becomes the node type in the graph. |
| `label` | Display name (e.g. "Enrich via API"). |
| `description` | Short description for palette and config panel. |
| `category` | Palette category: `sources` \| `processing` \| `sinks` \| `integration` \| `custom`. |
| `inputs` | List of **input ports**: `{ id, label?, type?, required? }`. `type` could be e.g. `records`, `file_path`, `json`, `any`. |
| `outputs` | List of **output ports**: `{ id, label?, type? }`. |
| `config_keys` | Optional list of config keys (env/study config) this node uses (like current NODE_CONFIG). |
| `code` | The runnable code (e.g. Python) or a reference to a script. See below. |
| `version` | Optional; for safe updates and debugging. |
| `handles_sensitive_data` | If `true`, the component's inputs/outputs may contain PII or sensitive data. When the **data proxy** is enabled (MCP, `MCP_DATA_PROXY_ENABLED=1`), such data is **masked** for AI users; the real app and pipeline runs always use unmasked data. See §3.1. |

**Data contract**: edges connect **output port → input port**. The runtime passes the value from the upstream output to the downstream input by port id (or by position if we keep single in/out per node for simplicity).

**Code**: Either (a) inline Python string, or (b) path to a file under a known directory (e.g. `components/` or `study_components/{study_id}/`). The runner would load and execute it in a defined way (see Execution below).

### 3.1 Sensitive data and the data proxy

- **`handles_sensitive_data`**: Custom components can set this flag when they process PII or other sensitive data (e.g. survey responses, contact info). Built-ins like `qualtrics` and `process` set it by default.
- **Data proxy (MCP)**: When `MCP_DATA_PROXY_ENABLED=1`, the MCP server replaces real data with **mock data** (same structure, safe values) for tools that return sensitive content. That includes:
  - **`qual_component_run_debug`**: The tool runs the real component code, then returns **mocked outputs** to the AI user so they can develop and test pipelines without seeing real data.
- **Real app**: Pipeline runs in the backend and the UI always use **unmasked** data; the proxy applies only to MCP tool responses for AI/LLM consumers.

---

## 4. Where Components Live (Registry)

Options:

- **A) File-based registry**  
  - Directory e.g. `components/` (or `config/components/`).  
  - Each component = a folder or a single file (e.g. `enrich_api.yaml` + `enrich_api.py`, or one `.component.json` with metadata + embedded code).  
  - Pro: versionable, no DB. Con: need to scan/parse; multi-user edits need filesystem or sync.

- **B) Database (datastore)**  
  - Tables: `components` (id, study_id or null for global, label, description, category, inputs, outputs, config_keys, code, version, created_at, updated_at).  
  - Pro: per-study or global components, easy to list/update via API. Con: need migrations and API.

- **C) Hybrid**  
  - **Built-in** components (qualtrics, box, grid, process, etc.) stay in code.  
  - **Custom** components live in DB (or files under `study_components/{study_id}/`).  
  - Pipeline validation: allow node type if it’s in `ALLOWED_NODE_TYPES` (built-in) **or** in the component registry for that study (and optionally global).

Recommendation: start with **file-based** for custom components (e.g. `components/*.component.json` plus optional `components/*.py`) so the MCP can read/write with normal file tools; add a **list** endpoint that merges built-ins (from code) with discovered file-based components. DB can come later if you need per-study or UI-managed components.

---

## 5. Execution: How the Pipeline Runs a Custom Node

Today the pipeline gets `PIPELINE_STEP_ORDER` and `PIPELINE_STEP_TYPES` and runs a fixed sequence of functions. For custom components:

1. **Resolve component**  
   For each step type that is not a built-in, load the component definition (from registry/file). If not found, fail the run with a clear error.

2. **Build context for the step**  
   - **Inputs**: From the previous step(s). Today we have a linear chain; you could keep that and pass “previous step output” as a single input (e.g. `records`), or later support multiple incoming edges and map by port id.  
   - **Config**: Study/config key-value (e.g. env) for `config_keys`.  
   - **Outputs**: Whatever the node’s code returns, structured by the component’s `outputs` (e.g. a dict mapping output id → value).

3. **Run the code**  
   - **Sandbox**: Run user code in a subprocess or restricted executor (e.g. only allow certain imports, no network unless declared). For MVP, running in the same process with a fixed signature is simpler but less safe.  
   - **Signature**: e.g. `run(inputs: dict, config: dict) -> dict`. The runner passes `inputs` (e.g. `{"records": normalized_records}`) and `config` (env/subset), and expects a dict of output id → value.  
   - **Persistence**: If the next step needs “records”, the runner passes the previous step’s output under that key. Built-in steps (qualtrics, process, grid, box) would be adapted to the same convention so custom nodes can sit between or after them.

4. **Order and data flow**  
   - Keep topological order from `validate_pipeline`.  
   - For each step in order: resolve inputs from predecessor step outputs (and optionally from “global” context like export path); run the step; store outputs by output id for the next steps.

This implies **built-in nodes** also expose a small adapter: e.g. qualtrics outputs `{"export_path": str, "videos_info": list}`, process takes `records` (or export_path + videos_info) and outputs `{"records": list, "processed_store": ...}`, etc. Custom nodes then consume and produce the same kind of structure.

---

## 6. MCP Tools for the AI (Create / Debug / Reuse)

So the MCP AI can **create**, **edit**, and **debug** components:

| Tool | Purpose |
|------|--------|
| `qual_components_list` | List available components (built-in + custom). Returns id, label, category, inputs, outputs, has_code. |
| `qual_component_get` | Get full definition (including code) for a component id. |
| `qual_component_create` | Create a new component (metadata + code). Requires confirmation if overwriting. |
| `qual_component_update` | Update metadata and/or code. |
| `qual_component_run_debug` | Run a component with **sample input** (and optional config) and return output or error. No pipeline run; used to verify code. |
| `qual_component_validate` | Validate component (syntax, required fields, input/output types if specified). |

**Creating a new node that can be reused** would look like:

1. User or AI defines: id, label, inputs (e.g. `records`), outputs (e.g. `records`), and code.  
2. Call `qual_component_create` (or update).  
3. Component appears in the palette (once the frontend reads from the same registry).  
4. User adds the node to a pipeline and wires it; on run, the pipeline runner loads and executes the component.

**Debugging**:

1. AI or user gets sample input (e.g. one record from a real run, or a minimal fixture).  
2. Call `qual_component_run_debug` with component id and that input.  
3. Inspect return value or error; fix code and repeat.

---

## 7. Frontend Implications

- **Palette**: In addition to hardcoded `NODE_CATEGORIES`, fetch custom components (e.g. from `GET /api/studies/{id}/components` or a global list). Render them in a “Custom” or per-category section; node type = component `id`.  
- **Config panel**: For custom components, show `config_keys` and allow editing (same as today’s study config). Optionally show “Edit code” that opens an MCP-assisted flow or deep link.  
- **Node appearance**: Either reuse `stage` and show `label` + “Custom” badge, or add a `custom` node type that looks slightly different (e.g. icon).  
- **Validation**: When saving a pipeline, backend already validates node types; once custom components are in the registry, allowed types = built-in + registry ids.

---

## 8. Open Questions / Tradeoffs

1. **Single vs multiple ports**  
   - Single input/output (like today) keeps the UI and execution simple; data is “one blob” (e.g. `records`) passed along.  
   - Multiple ports allow richer graphs (e.g. two inputs merged). Start with single in/out; extend later with port ids on edges.

2. **Code language and sandbox**  
   - Python is consistent with the rest of the pipeline. Sandboxing (subprocess, restricted imports, or a real sandbox) is important if untrusted users can add components.  
   - For “only our team / MCP” usage, running in-process with a fixed `run(inputs, config) -> dict` may be enough for an MVP.

3. **Built-ins vs custom**  
   - Easiest path: keep qualtrics, box, grid, process as built-in (no code in registry), and add a **parallel** “custom” path that uses the registry and the generic runner.  
   - Later you could describe built-ins with the same schema (inputs/outputs) so the graph model is uniform.

4. **Where does “standard” live?**  
   - “Standard” could mean: (a) shipped with the app (built-in), or (b) “blessed” custom components in a shared repo or default folder. Having a single registry (file or DB) that lists both built-ins and custom, with a `source: builtin | custom`, keeps the model clear.

5. **Versioning**  
   - Component `version` helps the AI and users know what changed. Optional for v1; add when you need “run with this version” or rollback.

---

## 9. Suggested Phases

- **Phase 1 (MVP)**  
  - Component schema (metadata + code) in files under `components/`.  
  - Registry loader: list + get by id; built-in types still in code.  
  - Pipeline runner: for node types that exist in the registry, load and run `run(inputs, config)`; built-ins unchanged.  
  - One or two custom components (e.g. “passthrough” or “filter”) to validate the loop.  
  - MCP: `qual_components_list`, `qual_component_get`, `qual_component_run_debug` (read-only + debug).

- **Phase 2**  
  - MCP: `qual_component_create`, `qual_component_update`, `qual_component_validate`.  
  - Frontend: palette and config for custom components; allow adding them to pipelines.

- **Phase 3**  
  - Multiple inputs/outputs and port-aware edges if needed.  
  - Sandboxing and safety.  
  - Optional: move custom components to DB and add UI for editing metadata (code still via MCP or file).

---

If you want to go deeper next, we can: (1) lock the component schema (e.g. one concrete JSON example), (2) sketch the exact `run(inputs, config)` contract and how built-ins are adapted, or (3) define the MCP tool signatures and one example “create component” flow.
