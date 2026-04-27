"""
Sandbox runner: execute custom component code in an isolated subprocess.
Uses a restricted API (input/config/output/log only); no arbitrary imports or I/O.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

from backend.pipeline.components.base import RunContext

log = logging.getLogger(__name__)

# Default timeout for custom component run (seconds)
DEFAULT_TIMEOUT = 300


def run_custom_component(
    code: str,
    inputs: dict,
    config: dict,
    context: RunContext,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Run custom component code in a subprocess with restricted API.

    - code: Python source that uses the global 'pipeline' (input, config, output, log).
    - inputs: map from input port id to value (must be JSON-serializable).
    - config: map from config key to value (must be JSON-serializable).
    - context: run context (logger used for sandbox logs).
    - timeout_seconds: kill subprocess after this many seconds.

    Returns: map from output port id to value.
    Raises: ValueError if payload invalid; RuntimeError if subprocess fails or times out.
    """
    payload = {"inputs": inputs, "config": config, "code": code}
    try:
        payload_str = json.dumps(payload)
    except TypeError as e:
        raise ValueError(f"Inputs or config are not JSON-serializable: {e}") from e

    bootstrap = Path(__file__).resolve().parent / "sandbox_bootstrap.py"
    if not bootstrap.exists():
        raise RuntimeError(f"Sandbox bootstrap not found: {bootstrap}")

    cmd = [sys.executable, str(bootstrap)]
    # Minimal env: no parent secrets; PYTHONSAFEPATH=1 (3.11+) avoids importing from cwd
    env = {"PYTHONSAFEPATH": "1"} if sys.version_info >= (3, 11) else {}
    try:
        proc = subprocess.run(
            cmd,
            input=payload_str.encode("utf-8"),
            capture_output=True,
            timeout=timeout_seconds,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            env=env,
        )
    except subprocess.TimeoutExpired:
        if context.logger:
            context.logger.error("Custom component timed out after %s seconds", timeout_seconds)
        raise RuntimeError(f"Custom component timed out after {timeout_seconds}s") from None

    out = proc.stdout.decode("utf-8", errors="replace").strip()
    err = proc.stderr.decode("utf-8", errors="replace").strip()
    if err and context.logger:
        context.logger.debug("Sandbox stderr: %s", err)

    if proc.returncode != 0:
        try:
            result = json.loads(out) if out else {}
        except json.JSONDecodeError:
            result = {"error": out or err or f"Subprocess exited with {proc.returncode}"}
        msg = result.get("error", out or err or f"Exit code {proc.returncode}")
        for line in result.get("logs", []):
            if context.logger:
                context.logger.info("[custom] %s", line)
        raise RuntimeError(f"Custom component failed: {msg}") from None

    try:
        result = json.loads(out)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Sandbox returned invalid JSON: {e}") from e

    if not result.get("ok"):
        msg = result.get("error", "Unknown error")
        for line in result.get("logs", []):
            if context.logger:
                context.logger.info("[custom] %s", line)
        raise RuntimeError(f"Custom component failed: {msg}") from None

    for line in result.get("logs", []):
        if context.logger:
            context.logger.info("[custom] %s", line)

    return result.get("outputs") or {}
