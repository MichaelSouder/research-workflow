"""
Bootstrap for custom component sandbox (runs in subprocess).
Reads JSON from stdin: { "inputs", "config", "code" }.
Exposes only a restricted 'pipeline' API; executes user code with safe builtins.
Writes JSON to stdout: { "ok": true, "outputs": {...} } or { "ok": false, "error": "..." }.
"""

import json
import sys

# Safe builtins: no I/O, no import, no eval/exec, no subprocess
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "hasattr": hasattr,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "None": None,
    "True": True,
    "False": False,
    "Exception": Exception,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "TypeError": TypeError,
    "AttributeError": AttributeError,
    "StopIteration": StopIteration,
}


class PipelineAPI:
    """Restricted API exposed to user code as 'pipeline'."""

    __slots__ = ("_inputs", "_config", "_outputs", "_logs")

    def __init__(self, inputs: dict, config: dict):
        self._inputs = inputs
        self._config = config
        self._outputs: dict = {}
        self._logs: list[str] = []

    def input(self, port_id: str):
        """Read value for an input port."""
        if port_id not in self._inputs:
            raise KeyError(f"Unknown input port: {port_id!r}")
        return self._inputs[port_id]

    def config(self, key: str):
        """Read a config value."""
        return self._config.get(key)

    def output(self, port_id: str, value) -> None:
        """Set an output port value (must be JSON-serializable)."""
        self._outputs[port_id] = value

    def log(self, message: str) -> None:
        """Append a log line (passed back to runner)."""
        self._logs.append(str(message))

    def get_outputs(self) -> dict:
        return self._outputs

    def get_logs(self) -> list[str]:
        return self._logs


def _json_serializable(obj) -> bool:
    """Check if object is JSON-serializable (recursive for dict/list)."""
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def main() -> None:
    if sys.stdin.isatty():
        sys.stderr.write("sandbox_bootstrap: expected JSON on stdin\n")
        sys.exit(2)
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        result = {"ok": False, "error": f"Invalid JSON stdin: {e}"}
        sys.stdout.write(json.dumps(result) + "\n")
        sys.exit(1)

    inputs = payload.get("inputs") or {}
    config = payload.get("config") or {}
    code = payload.get("code")
    if not code or not isinstance(code, str):
        result = {"ok": False, "error": "Missing or invalid 'code' in payload"}
        sys.stdout.write(json.dumps(result) + "\n")
        sys.exit(1)

    api = PipelineAPI(inputs, config)
    globals_dict = {"pipeline": api, "__builtins__": SAFE_BUILTINS}

    try:
        exec(code, globals_dict)
    except Exception as e:
        result = {"ok": False, "error": f"{type(e).__name__}: {e}", "logs": api.get_logs()}
        sys.stdout.write(json.dumps(result) + "\n")
        sys.exit(1)

    outputs = api.get_outputs()
    for k, v in outputs.items():
        if not _json_serializable(v):
            result = {
                "ok": False,
                "error": f"Output port {k!r} value is not JSON-serializable",
                "logs": api.get_logs(),
            }
            sys.stdout.write(json.dumps(result) + "\n")
            sys.exit(1)

    result = {"ok": True, "outputs": outputs, "logs": api.get_logs()}
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
