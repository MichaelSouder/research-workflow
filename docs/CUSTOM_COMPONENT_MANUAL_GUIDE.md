# Manual guide: implementing a custom pipeline component

This guide explains how to **manually** create a custom pipeline component: where to put it, what the file must contain, and how to write the code that runs inside the sandbox.

---

## 1. Overview

A **custom component** is a pipeline node type you define yourself. It has:

- **Manifest**: metadata (id, label, inputs, outputs, config keys, etc.) so the pipeline runner and UI know how to wire it.
- **Code**: Python that runs in a **restricted sandbox** with only a small API (`pipeline.input`, `pipeline.config`, `pipeline.output`, `pipeline.log`). No filesystem, no network, no arbitrary imports.

Custom components live as **one JSON file per component** in `backend/custom_components/` by default (same repo root, under `backend`). You can override the directory with `CUSTOM_COMPONENTS_DIR`. After you add or change a file, the app picks up the component when it next lists or runs components (registry reloads on demand).

---

## 2. Where to put the file

| Item | Value |
|------|--------|
| **Directory** | `backend/custom_components/` by default (or `CUSTOM_COMPONENTS_DIR`) |
| **Filename** | `{component_id}.json` |
| **Example** | Component id `my_filter` → file `backend/custom_components/my_filter.json` |

The directory is created automatically the first time a component is loaded. Do **not** use a component id that matches a built-in: `qualtrics`, `process`, `grid`, `box` are reserved.

---

## 3. Component ID rules

- **Required**: Non-empty string.
- **Pattern**: Must **start with a letter** and contain only **letters, numbers, and underscores** (`[a-zA-Z][a-zA-Z0-9_]*`).
- **Reserved**: These ids are built-in and cannot be used: `qualtrics`, `process`, `grid`, `box`.

Valid: `my_filter`, `enrich_api`, `step_1`. Invalid: `123_foo` (starts with number), `my-filter` (hyphen), `qualtrics` (reserved).

---

## 4. File format: single JSON file

Each component is **one JSON file** with two top-level keys:

| Key | Type | Description |
|-----|------|--------------|
| `manifest` | object | Metadata (id, label, inputs, outputs, etc.). See §5. |
| `code` | string | Python source code that runs in the sandbox. See §7. |

Minimal example:

```json
{
  "manifest": {
    "id": "my_filter",
    "label": "My Filter",
    "description": "Filters records by a simple rule.",
    "category": "custom",
    "inputs": [{"id": "default", "type": "any", "required": true}],
    "outputs": [{"id": "default", "type": "any"}],
    "config_keys": [],
    "handles_sensitive_data": false
  },
  "code": "data = pipeline.input(\"default\")\npipeline.output(\"default\", data)"
}
```

---

## 5. Manifest fields (full reference)

All fields that can appear in `manifest`:

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Unique component id; must match filename stem (`{id}.json`) and ID rules (§3). |
| `label` | string | Yes | Display name (e.g. in the pipeline editor). |
| `description` | string | No | Short description (default `""`). |
| `category` | string | No | Category for the palette: `sources`, `processing`, `sinks`, `integration`, or `custom` (default `custom`). |
| `inputs` | array | No | List of input ports (default `[]`; see §6). |
| `outputs` | array | No | List of output ports (default `[]`; see §6). |
| `config_keys` | array | No | List of config key names the component uses (default `[]`). |
| `version` | string | No | Optional version string (e.g. `"1.0"`). |
| `handles_sensitive_data` | boolean | No | If `true`, component I/O may contain PII; when the data proxy is enabled (MCP), that data is masked for AI users (default `false`). |

**Note:** `source` is set to `"custom"` by the loader; you do not need to include it.

---

## 6. Input and output ports

Each **input port** is an object:

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Port id (e.g. `default`, `records`, `file_path`). |
| `label` | string | No | Display label. |
| `type` | string | No | One of: `records`, `file_path`, `blob`, `any` (default `any`). |
| `required` | boolean | No | Whether the input must be provided (default `true`). |

Each **output port** is an object:

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Port id. |
| `label` | string | No | Display label. |
| `type` | string | No | Same as input: `records`, `file_path`, `blob`, `any` (default `any`). |

**Port types (semantic):**

- `records`: list of dicts (e.g. survey responses, normalized rows).
- `file_path`: string path to a file.
- `blob`: arbitrary JSON-serializable value.
- `any`: no schema; use when type is flexible.

**How data flows in a pipeline:**  
Edges connect **output port → input port**. The runner passes the upstream component’s output (by port id) into the downstream component’s inputs. The first component in the graph typically gets empty inputs; downstream components usually receive the previous step’s output on a port such as `default`.

---

## 7. Sandbox code: the only API you have

Your `code` string is executed in an **isolated subprocess** with a single global object: **`pipeline`**. You must **not** use `import`, `open`, `os`, `subprocess`, `eval`, `exec`, or any network/filesystem APIs. Only the following are available.

### 7.1 `pipeline.input(port_id)`

Returns the value for the given **input port id**.  
If the port was not provided or is missing, this can raise `KeyError`. Check inputs if your component allows optional ports.

```python
# Single upstream data (common case)
data = pipeline.input("default")

# Multiple named inputs (if you declared them)
records = pipeline.input("records")
path = pipeline.input("file_path")
```

### 7.2 `pipeline.config(key)`

Returns the value for the given **config key** (from study/app config). Keys should be listed in `manifest.config_keys`. Returns `None` if the key is missing.

```python
threshold = pipeline.config("MY_THRESHOLD")
if threshold is None:
    threshold = 10
```

### 7.3 `pipeline.output(port_id, value)`

Sets the value for an **output port**. You must call this for every output port you declare; values must be **JSON-serializable** (dict, list, str, int, float, bool, None). Non-serializable values cause the run to fail.

```python
pipeline.output("default", result)
# Or multiple ports
pipeline.output("records", filtered_list)
pipeline.output("count", len(filtered_list))
```

### 7.4 `pipeline.log(message)`

Appends a log line (string). Shown in activity/logs for the run.

```python
pipeline.log("Filtering with threshold " + str(threshold))
```

### 7.5 Allowed builtins

Only these builtins are available (no `open`, `import`, etc.):

`abs`, `all`, `any`, `bool`, `dict`, `divmod`, `enumerate`, `filter`, `float`, `hasattr`, `int`, `isinstance`, `len`, `list`, `map`, `max`, `min`, `pow`, `range`, `reversed`, `round`, `set`, `sorted`, `str`, `sum`, `tuple`, `type`, `zip`, and exceptions such as `ValueError`, `KeyError`, `TypeError`, etc.

---

## 8. Full example: a “filter by count” component

**File:** `backend/custom_components/filter_by_count.json`

```json
{
  "manifest": {
    "id": "filter_by_count",
    "label": "Filter by count",
    "description": "Keeps only the first N items from the default input.",
    "category": "custom",
    "inputs": [
      {"id": "default", "label": "Data", "type": "any", "required": true}
    ],
    "outputs": [
      {"id": "default", "label": "Filtered data", "type": "any"}
    ],
    "config_keys": ["FILTER_MAX_COUNT"],
    "handles_sensitive_data": false
  },
  "code": "data = pipeline.input(\"default\")\nn = pipeline.config(\"FILTER_MAX_COUNT\")\nif n is not None:\n  try:\n    n = int(n)\n  except (TypeError, ValueError):\n    n = 100\nelse:\n  n = 100\nif isinstance(data, list):\n  out = data[:n]\nelse:\n  out = data\npipeline.log(\"Filtered to \" + str(len(out)) + \" items\")\npipeline.output(\"default\", out)"
}
```

Pretty-printed code for readability:

```python
data = pipeline.input("default")
n = pipeline.config("FILTER_MAX_COUNT")
if n is not None:
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 100
else:
    n = 100
if isinstance(data, list):
    out = data[:n]
else:
    out = data
pipeline.log("Filtered to " + str(len(out)) + " items")
pipeline.output("default", out)
```

---

## 9. Step-by-step: creating a component manually

1. **Choose an id**  
   Must start with a letter; only letters, numbers, underscores; not `qualtrics`, `process`, `grid`, `box`.

2. **Create the directory** (if needed):
   ```bash
   mkdir -p backend/custom_components
   ```

3. **Create `backend/custom_components/{id}.json`**  
   One JSON object with `manifest` and `code` as in §4 and §5. Ensure:
   - `manifest.id` equals the filename stem.
   - Every declared output port is set with `pipeline.output(port_id, value)` in code.
   - All output values are JSON-serializable.

4. **Test with run_debug (optional)**  
   From the app or MCP, use `qual_component_run_debug` with sample `inputs_json` and `config_json` to run your code and inspect outputs without running a full pipeline.

5. **Use in a pipeline**  
   Add a node with type = your component id in the pipeline graph and wire edges to/from its ports. The runner will load your component from `backend/custom_components/{id}.json` (or `CUSTOM_COMPONENTS_DIR/{id}.json`) and execute the sandbox code with the inputs and config provided by the pipeline.

---

## 10. Reloading and validation

- **Loading**: Components are loaded when the pipeline registry is first used (e.g. listing components or running a pipeline). Custom components are read from `backend/custom_components/*.json` by default (or `${CUSTOM_COMPONENTS_DIR}/*.json` if set).
- **After editing**: Save the JSON file. The next list/run that uses the registry will see the updated manifest and code (no separate “reload” step in manual workflow; if you use MCP create/update/delete, the registry reloads automatically).
- **Validation**: When the file is loaded, `id` must match the filename and satisfy the ID pattern; built-in ids are rejected. Invalid JSON or missing `manifest.id`/`manifest.label` cause the component to be skipped (and not registered).

---

## 11. Sensitive data and the data proxy

- Set **`handles_sensitive_data`: true** in the manifest if your component processes PII or other sensitive data.
- When **MCP_DATA_PROXY_ENABLED=1**, the MCP server masks sensitive tool responses for AI users. For example, `qual_component_run_debug` returns **mocked outputs** (same structure, safe values) so the AI never sees real data. The real app and pipeline runs always use unmasked data.

---

## 12. Summary checklist

- [ ] File path: `backend/custom_components/{component_id}.json` (or `${CUSTOM_COMPONENTS_DIR}/{component_id}.json`).
- [ ] Component id: starts with letter, only letters/numbers/underscores; not a built-in id.
- [ ] Top-level keys: `manifest` (object) and `code` (string).
- [ ] Manifest has at least: `id`, `label`; optionally `description`, `category`, `inputs`, `outputs`, `config_keys`, `version`, `handles_sensitive_data`.
- [ ] Code uses only `pipeline.input`, `pipeline.config`, `pipeline.output`, `pipeline.log` and allowed builtins.
- [ ] Every output port declared in `manifest.outputs` is set exactly once with `pipeline.output(port_id, value)`.
- [ ] All output values are JSON-serializable (no custom classes, no file handles, etc.).

For design context and execution contract details, see [DESIGN_CUSTOM_COMPONENTS.md](./DESIGN_CUSTOM_COMPONENTS.md) and the pipeline component spec (e.g. resource `spec://pipeline/components` in the MCP server).
