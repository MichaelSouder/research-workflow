# Architecture Overhaul: Component-First Pipeline

Every unit of functionality and its data interfaces are **discrete components**. The pipeline is a graph of components; the runner is generic and does not special-case any node type.

---

## 1. Principle

- **One abstraction**: A *component* is the only unit of pipeline logic. There are no "built-in special cases" in the runner—only components that happen to be shipped in code vs loaded from a registry.
- **Explicit data contract**: Each component declares **inputs** (name, type, required) and **outputs** (name, type). Edges carry data from output port to input port. No implicit "whatever the previous step returned."
- **Single execution contract**: Every component is invoked the same way: `run(inputs: dict, config: dict, context: RunContext) -> dict`. The runner gathers inputs from upstream outputs, calls `run`, and passes the returned dict to downstream components.

---

## 2. Component Interface (Discrete Unit)

Every component—whether qualtrics, process, grid, box, or a custom node—is defined by:

### 2.1 Manifest (metadata)

| Field | Purpose |
|-------|--------|
| `id` | Unique type id (e.g. `qualtrics`, `process`, `grid`, `box`, `enrich_api`). |
| `label` | Display name. |
| `description` | Short description. |
| `category` | `sources` \| `processing` \| `sinks` \| `integration` \| `custom`. |
| `inputs` | List of input ports: `{ id, label?, type?, required? }`. |
| `outputs` | List of output ports: `{ id, label?, type? }`. |
| `config_keys` | Config/env keys this component uses. |
| `source` | `builtin` \| `custom` (where the definition lives). |
| `version` | Optional. |

### 2.2 Execution contract

- **Signature**: `run(inputs: dict, config: dict, context: RunContext) -> dict`
  - `inputs`: Map from **input port id** to value. The runner fills this from upstream components’ outputs (and optionally from shared context, e.g. study id).
  - `config`: Map of config key → value (env/study config for this run).
  - `context`: RunContext with run id, study id, logger, paths (e.g. workspace, export dir), and any shared state the runner provides.
  - **Returns**: Dict from **output port id** to value. Downstream components receive these by port id.

- **Rules**:
  - Component must not depend on execution order of other components except via `inputs`.
  - Side effects (API calls, file writes) are allowed; context can provide paths and credentials via config.
  - If a component fails, it raises; the runner fails the run and can report which component failed.

### 2.3 Data types (for inputs/outputs)

Keep simple at first:

- `records`: list of dicts (e.g. survey responses / normalized rows).
- `file_path`: string path to a file (e.g. export JSON).
- `blob`: arbitrary JSON-serializable value.
- `any`: no schema.

Types are for documentation and optional validation; the runner passes values through. Later you can add validation (e.g. JSON Schema) per port.

---

## 3. Current Steps as Discrete Components

Refactor each existing step into the same interface. Example mapping:

### 3.1 Qualtrics (source)

- **Inputs**: none (or a single optional `trigger` for future use).
- **Outputs**: `export_path` (file_path), `videos_info` (records).
- **Config**: `QUALTRICS_API_TOKEN`, `QUALTRICS_SURVEY_ID`, `QUALTRICS_DATA_CENTER`, etc.
- **Logic**: Current `_run_qualtrics()` moves into a component module; it returns `{"export_path": path, "videos_info": list}`.

### 3.2 Process (normalize + duplicate_skip + fraud)

- **Inputs**: `videos_info` (records), `export_path` (file_path).
- **Outputs**: `records` (records), `processed_store` (blob or internal handle).
- **Config**: `DUPLICATE_SKIP_ENABLED`, `PROCESSED_IDS_PATH`, `FRAUD_*`, etc.
- **Logic**: Current `_run_process()` becomes the component body; it reads from `inputs["videos_info"]` and `inputs["export_path"]`, returns `{"records": normalized_records, "processed_store": ...}`.

### 3.3 Grid

- **Inputs**: `records` (records). Optionally `processed_store` if it needs to mark completed.
- **Outputs**: e.g. `records` (same or enriched with grid ids), or `grid_results` (blob).
- **Config**: `GRID_API_TOKEN`, `GRID_STUDY_ID`.
- **Logic**: Current grid logic in `_run_grid_box` becomes a component; takes `inputs["records"]`, returns a defined output dict.

### 3.4 Box

- **Inputs**: `records` (records), and optionally `export_path` or file paths from context.
- **Outputs**: e.g. `uploaded` (blob) or pass-through `records`.
- **Config**: `BOX_ROOT_FOLDER_ID`, `BOX_CONFIG_PATH`, etc.
- **Logic**: Current box logic in `_run_grid_box` becomes its own component; takes `inputs["records"]` (and any paths from context/config), returns a defined output dict.

After this, **grid** and **box** can be separate nodes in the graph; the runner wires data by port id (e.g. process outputs `records` → grid inputs `records`; process outputs `records` → box inputs `records`). No more monolithic `_run_grid_box`.

---

## 4. Generic Pipeline Runner

The runner no longer knows about qualtrics or box; it only knows:

1. **Graph**: nodes (with component `id` per node) and edges (source node + output port → target node + input port). If port ids are omitted, assume a single default port per node (e.g. `default` in / out).
2. **Topological order**: from `validate_pipeline` (or a DAG sort that respects edges).
3. **Per step**:
   - Resolve **inputs**: for each input port, find the edge(s) from upstream; take the value from that upstream node’s output port. If multiple edges to the same input, define a rule (e.g. merge list, or last writer).
   - Load **component** by type id (from registry).
   - Call `component.run(inputs, config, context)`.
   - Store the returned dict as this node’s **outputs** (keyed by output port id) for downstream steps.

Shared context (e.g. `export_path` for the whole run, or `processed_store`) can be:
- Passed as extra keys in `inputs` by the runner (e.g. “inject context into every component”), or
- Carried in `RunContext` and components read it from there.

Prefer explicit inputs so the graph is self-describing; use context for run-scoped things (logger, paths, study id).

---

## 5. Registry: One Place for All Components

- **Registry** returns a list of component manifests (id, label, inputs, outputs, config_keys, source, version). For each id, the runner can get the **runner** (the callable or module that implements `run(...)`).
- **Built-in components**: Implemented in code (e.g. `pipeline/components/qualtrics.py`, `process.py`, `grid.py`, `box.py`). Each module exports a manifest and a `run` function. The registry loads these at startup or first use.
- **Custom components**: Same manifest shape + code (inline or file). Stored in files (e.g. `components/*.component.json` + `*.py`) or DB. Registry merges built-in + custom when listing or resolving.

Validation (e.g. `validate_pipeline`) allows a node type if and only if the registry has a component for that id. So allowed types = registry.keys().

---

## 6. File Layout (Proposed)

```
pipeline/
  components/
    __init__.py          # Registry: list, get(id), get_runner(id)
    base.py              # RunContext, abstract run(inputs, config, context) -> dict
    qualtrics.py         # Manifest + run() for qualtrics
    process.py           # Manifest + run() for process (normalize + duplicate_skip + fraud)
    grid.py              # Manifest + run() for grid
    box.py               # Manifest + run() for box
  run.py                 # Generic runner: topo order, resolve inputs, call component.run(), pass outputs
  ...
```

Custom components (later) can live under `components/custom/` or a configurable path, with the same manifest + `run` contract (loaded dynamically).

---

## 7. Edge Model and Ports

- **Today**: Edges are (source_node_id, target_node_id). Data is implicitly “whatever the source step produced.”
- **After overhaul**: Edges are (source_node_id, source_output_port_id, target_node_id, target_input_port_id). Default port ids (e.g. `default`) allow a single in/out per node so existing graphs keep working.
- **Runner**: When building `inputs` for a node, for each input port, find edges whose target is this node and target_input_port_id matches; take the value from the source node’s output for source_output_port_id. Single port = single default id.

---

## 8. Migration Path

1. **Define** `RunContext`, the component manifest type, and the `run(inputs, config, context) -> dict` contract in `pipeline/components/base.py`.
2. **Add** `pipeline/components/registry.py` (or inside `__init__.py`): register built-in components by id, expose list and get_runner.
3. **Implement** one component end-to-end (e.g. **qualtrics**): manifest + `run()` that returns `{export_path, videos_info}`. No change to callers yet.
4. **Implement** **process** component: inputs `videos_info`, `export_path`; output `records` (and optionally `processed_store`). Refactor current `_run_process` into this.
5. **Split** grid and box into two components; refactor `_run_grid_box` into `grid.run()` and `box.run()` with clear inputs/outputs.
6. **Replace** the body of `pipeline/run.py` with the generic runner: get step order and types from env, for each step load component by type, build inputs from previous outputs (and default ports), call run(), store outputs. Remove all `_run_*` special cases.
7. **Update** validation to use registry: allowed node types = registry component ids.
8. **Optional**: Add port ids to edges in the API/frontend; default to `default` for backward compatibility.

---

## 9. Benefits of This Overhaul

- **Discrete components**: Every piece of functionality has one place, one interface, one contract.
- **Data interfaces are explicit**: Inputs and outputs are declared; the graph and runner are deterministic.
- **Custom components**: New nodes are just new components in the registry; no runner changes.
- **Testability**: Each component can be unit-tested with a dict of inputs and config; no pipeline needed.
- **MCP and AI**: List components, get manifest + code for custom ones, run a component with sample inputs for debugging. Same story for built-in vs custom.

---

## 10. Isolation and Safety for Custom Code Blobs

Custom component code (user- or AI-written) must be **isolated** and **restricted** so it cannot run dangerous operations.

### 10.1 Isolation: Subprocess Boundary

- **Built-in components** (qualtrics, process, grid, box): Run in the main pipeline process; they are trusted code we ship.
- **Custom components** (code blobs): Always run in a **separate Python subprocess** with:
  - **Timeout**: Process is killed after a configurable limit (e.g. 300 seconds).
  - **No shared memory**: Inputs and outputs are passed via JSON (stdin / stdout or temp files), so the child cannot access the parent’s state.
  - **Restricted environment**: Subprocess is started with a minimal env (e.g. `PYTHONSAFEPATH=1`), and no ability to read arbitrary env vars from the parent.

### 10.2 Restricted API: No Arbitrary Python

Custom code does **not** get full Python. It gets a single injected object (e.g. `pipeline`) with an **allowlisted API**:

| Method | Purpose |
|--------|--------|
| `pipeline.input(port_id)` | Read value for an input port (data from upstream). |
| `pipeline.config(key)` | Read a config value (only keys declared in the component’s `config_keys`). |
| `pipeline.output(port_id, value)` | Set an output port value (must be JSON-serializable). |
| `pipeline.log(message)` | Append a log line (passed back to runner; no arbitrary I/O). |

The child process **does not** have:

- `import` (or only a stub that raises).
- `open`, `os`, `subprocess`, `eval`, `exec`, `__import__`.
- Network (unless we add an explicit `pipeline.http_request(url, method, ...)` later that we control).
- File system access (except we could add a future `pipeline.read_file(path)` that only allows paths under a sandbox dir we pass in).

So “code blobs” are executed in a **restricted namespace**: the runner serializes `inputs` and `config` into the subprocess, runs the user’s code with only the `pipeline` object in scope, then reads back the outputs they set via `pipeline.output(...)`.

### 10.3 Implementation Sketch

- **Bootstrap script** (e.g. `pipeline/components/sandbox_bootstrap.py`): Runs inside the subprocess. Reads JSON from stdin (or a temp file path in env). Deserializes into `inputs` and `config`. Builds a `PipelineAPI` object that exposes only `input`, `config`, `output`, `log`. Executes the user’s code in a namespace where `pipeline` is this API and `__builtins__` is a minimal safe set (e.g. `len`, `str`, `list`, `dict`, `range`, `enumerate`, `isinstance`, `True`, `False`, `None`). After execution, writes the collected outputs as JSON to stdout (or temp file). Any exception is serialized and written so the parent can raise or report.
- **Parent** (runner): Spawns subprocess with timeout, writes inputs to child’s stdin, reads stdout (or temp file). On timeout, kills the process. Parses output or error and either returns the output dict or raises.

### 10.4 What We Explicitly Disallow (Dangerous Operations)

- **No** arbitrary module imports (no `os`, `sys`, `subprocess`, `socket`, etc.).
- **No** file system access (no `open`, `Path`, `pathlib`) unless we add a controlled API later.
- **No** network access from user code unless we add a controlled `pipeline.http_*` helper.
- **No** subprocess / shell (no `os.system`, `subprocess.run`, `eval`, `exec` of dynamic strings).
- **No** unbounded CPU or memory: timeout and process kill mitigate runaway loops; we can add memory limits (e.g. `resource` on Unix) later.

### 10.5 Summary

- **Isolation**: Custom code runs in a separate process with timeout and no shared state.
- **Safety**: Custom code only sees a restricted `pipeline` API; no general Python builtins for I/O, import, or subprocess. Dangerous operations are disallowed by design.

---

## 11. Relation to DESIGN_CUSTOM_COMPONENTS.md

- **DESIGN_CUSTOM_COMPONENTS.md** describes how to add *custom* components (metadata + code, registry, MCP tools). The **component-first overhaul** makes that the *only* model: built-ins are just components that ship in code. So:
  - Implement the overhaul (every step is a component with explicit in/out).
  - Then custom components are “components that are not built-in” and are loaded from the registry from files or DB; the same runner runs them.
  - MCP tools (list, get, create, update, run_debug, validate) apply to all components; for built-ins, create/update might be no-ops or admin-only.
  - **Custom code blobs** run isolated in a subprocess with a restricted API (Section 10); they cannot run dangerous operations.

This gives you one architecture: discrete components, explicit data interfaces, and safe isolation for custom code.
