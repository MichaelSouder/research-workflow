"""
Run state, config store, and pipeline runner.
Shared by all API routes; preserves same behavior and response shapes.
Config is not read from or written to files; study config lives in the datastore.
"""

import json
import os
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from backend.datastore.base import Datastore

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = PROJECT_ROOT / "backend" / "qualtrics_box_task.py"
# Used only for one-time migration when no studies exist (migration.py).
CONFIG_FILE = PROJECT_ROOT / "ui_config.json"

# Run state (one run at a time; tied to study_id)
_run_id: str | None = None
_run_study_id: str | None = None
_run_db_id: str | None = None  # DB run id for logging (when datastore + study_id)
_datastore_for_logging: "Datastore | None" = None
_status: str = "idle"
_current_step: str = ""
_progress_percent: int = 0
_message: str = ""
_activity: list[dict] = []
_process: subprocess.Popen | None = None
_stop_requested: bool = False
_lock = threading.Lock()

# Distribution send (per study): busy flag and last result for UI
_distribution_busy: dict[str, bool] = {}
_distribution_last_result: dict[str, dict] = {}


def set_distribution_busy(study_id: str, busy: bool) -> None:
    with _lock:
        if busy:
            _distribution_busy[study_id] = True
        else:
            _distribution_busy.pop(study_id, None)


def get_distribution_busy(study_id: str) -> bool:
    with _lock:
        return _distribution_busy.get(study_id, False)


def set_distribution_last_result(study_id: str, result: dict) -> None:
    with _lock:
        _distribution_last_result[study_id] = result


def get_distribution_last_result(study_id: str) -> dict | None:
    with _lock:
        return _distribution_last_result.get(study_id)


SECRET_KEYS = {"QUALTRICS_API_TOKEN", "GRID_API_TOKEN", "BOX_CLIENT_SECRET"}
DEFAULT_CONFIG_KEYS = [
    "QUALTRICS_API_TOKEN",
    "QUALTRICS_SURVEY_ID",
    "QUALTRICS_DATA_CENTER",
    "GRID_API_TOKEN",
    "GRID_STUDY_ID",
    "BOX_ROOT_FOLDER_ID",
    "BOX_CONFIG_PATH",
    "DUPLICATE_SKIP_ENABLED",
    "PROCESSED_IDS_PATH",
    "SCHEDULE_ENABLED",
    "SCHEDULE_CRON",
    "SCHEDULE_TIMEZONE",
    "QUALTRICS_DIRECTORY_ID",
    "QUALTRICS_MAILING_LIST_ID",
    "QUALTRICS_LIBRARY_ID",
    "QUALTRICS_MESSAGE_ID_SMS",
    "QUALTRICS_MESSAGE_ID_EMAIL",
    "QUALTRICS_CONTACT_METHOD",
    "QUALTRICS_DISTRIBUTION_TIMEZONE",
    "QUALTRICS_DISTRIBUTION_TIME_SLOTS",
    "QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES",
]
FRAUD_CONFIG_KEYS = [
    "FRAUD_ENABLED",
    "FRAUD_SPEED",
    "FRAUD_DUPLICATE_IP",
    "FRAUD_STRAIGHTLINING",
    "FRAUD_INCOMPLETE",
]
FRAUD_CONFIG_DEFAULTS: dict[str, str] = {
    "FRAUD_ENABLED": "true",
    "FRAUD_SPEED": "true",
    "FRAUD_DUPLICATE_IP": "true",
    "FRAUD_STRAIGHTLINING": "true",
    "FRAUD_INCOMPLETE": "true",
}
DEFAULT_CONFIG_VALUES: dict[str, str] = {
    "QUALTRICS_SURVEY_ID": "SV_430r2OHphUatmzs",
    "QUALTRICS_DATA_CENTER": "yul1",
    "GRID_STUDY_ID": "372",
    "BOX_ROOT_FOLDER_ID": "334546874262",
    "BOX_CONFIG_PATH": str(PROJECT_ROOT / "box.config.json"),
    "DUPLICATE_SKIP_ENABLED": "true",
    "PROCESSED_IDS_PATH": str(PROJECT_ROOT / "backend" / "workspace" / "processed_response_ids.json"),
    "SCHEDULE_ENABLED": "false",
    "SCHEDULE_CRON": "0 9 * * *",
    "SCHEDULE_TIMEZONE": "America/Chicago",
    "QUALTRICS_DIRECTORY_ID": "",
    "QUALTRICS_MAILING_LIST_ID": "",
    "QUALTRICS_LIBRARY_ID": "",
    "QUALTRICS_MESSAGE_ID_SMS": "",
    "QUALTRICS_MESSAGE_ID_EMAIL": "",
    "QUALTRICS_CONTACT_METHOD": "email",
    "QUALTRICS_DISTRIBUTION_TIMEZONE": "America/Chicago",
    "QUALTRICS_DISTRIBUTION_TIME_SLOTS": "[]",
    "QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES": "10080",
}
_config: dict[str, str] = {}

GRID_BASE_URL = "https://lnpiapp.med.umn.edu/api/grid"


def load_config() -> None:
    """No-op: config is stored only in the datastore (study_config). Kept for API compatibility."""
    global _config
    _config = {}


def save_config() -> None:
    """No-op: config is not written to file. Study config is saved via PUT /api/studies/:id/config."""


def mask_value(key: str, value: str | None) -> str:
    if value is None or key in SECRET_KEYS or "TOKEN" in key or "SECRET" in key:
        return "********" if value else ""
    return value or ""


def append_activity(level: str, message: str, step: str = "") -> None:
    with _lock:
        step_val = step or _current_step
        _activity.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "step": step_val,
            }
        )
        run_db_id = _run_db_id
        store = _datastore_for_logging
    if run_db_id and store:
        try:
            store.append_run_log(run_db_id, level, message, step_val)
        except Exception:
            pass


def get_script_default(key: str) -> str | None:
    """Token/secret default from backend.pipeline.config or backend.qualtrics_box_task (for UI Show)."""
    if "TOKEN" not in key and key not in SECRET_KEYS:
        return None
    try:
        from backend.pipeline import config as pipeline_config

        return getattr(pipeline_config, key, None) or None
    except Exception:
        pass
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("backend.qualtrics_box_task", SCRIPT_PATH)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return getattr(mod, key, None) or None
    except Exception:
        pass
    return None


def get_status(study_id: str | None = None) -> dict:
    """Return run status. If study_id given, return status only when active run is for that study else idle."""
    with _lock:
        if study_id is not None and _run_study_id != study_id:
            return {
                "runId": None,
                "runStudyId": None,
                "status": "idle",
                "currentStep": "",
                "progressPercent": 0,
                "message": "",
            }
        return {
            "runId": _run_id,
            "runStudyId": _run_study_id,
            "status": _status,
            "currentStep": _current_step,
            "progressPercent": _progress_percent,
            "message": _message,
        }


def get_activity(study_id: str | None = None) -> dict:
    """Return activity list. If study_id given, return activity only when active run is for that study."""
    with _lock:
        if study_id is not None and _run_study_id != study_id:
            return {"activity": []}
        return {"activity": list(_activity)}


def get_errors(study_id: str | None = None) -> dict:
    """Return errors (and warnings). If study_id given, return only when active run is for that study."""
    with _lock:
        if study_id is not None and _run_study_id != study_id:
            return {"errors": []}
        errors = [a for a in _activity if a.get("level") in ("error", "warning")]
        return {"errors": errors}


def _merge_config_dict(config_dict: dict[str, str]) -> dict[str, str]:
    """Merge config dict with env, defaults, fraud defaults. Used for study config or global _config."""
    merged = {}
    for k in DEFAULT_CONFIG_KEYS:
        v = (config_dict.get(k) or os.environ.get(k) or DEFAULT_CONFIG_VALUES.get(k) or "")
        if not v and ("TOKEN" in k or k in SECRET_KEYS):
            script_val = get_script_default(k)
            if script_val:
                v = script_val
        merged[k] = v or ""
    for k in config_dict:
        if k not in merged:
            merged[k] = config_dict.get(k) or ""
    for k in FRAUD_CONFIG_KEYS:
        merged[k] = merged.get(k) or config_dict.get(k) or FRAUD_CONFIG_DEFAULTS.get(k) or "true"
    return merged


def get_merged_config(reveal_secrets: bool = False, config_override: dict[str, str] | None = None) -> dict:
    """
    Return merged config for API. If config_override given (e.g. from study), use that instead of _config.
    Keys: "config" (dict), "keys" (list). Same shape as GET /config response.
    """
    with _lock:
        base = config_override if config_override is not None else _config
        merged = _merge_config_dict(base)
        if reveal_secrets:
            result = {k: (merged.get(k) or "") for k in merged}
        else:
            result = {k: mask_value(k, (merged.get(k) or "")) for k in merged}
        return {"config": result, "keys": list(result.keys())}


def get_study_config_merged(study_config: dict[str, str]) -> dict[str, str]:
    """Return merged config dict (with env/defaults) for server-side use (e.g. pipeline, distribution). No mask."""
    return _merge_config_dict(study_config or {})


def get_merged_config_from_study_config(study_config: dict[str, str], reveal_secrets: bool = False) -> dict:
    """Return merged config (config + keys) from a study's config dict. No lock; stateless."""
    merged = _merge_config_dict(study_config)
    if reveal_secrets:
        result = {k: (merged.get(k) or "") for k in merged}
    else:
        result = {k: mask_value(k, (merged.get(k) or "")) for k in merged}
    return {"config": result, "keys": list(result.keys())}


def update_config(config: dict, persist: bool = False) -> None:
    """Update in-memory config. Persist is ignored (no file). Caller should refresh scheduler."""
    with _lock:
        _config.update(config)


def is_running(study_id: str | None = None) -> bool:
    """True if pipeline is running. If study_id given, True only when run is for that study."""
    with _lock:
        if _status != "running" or _process is None:
            return False
        if study_id is not None and _run_study_id != study_id:
            return False
        return True


def get_config_for_pipeline(config_dict: dict[str, str] | None = None) -> dict[str, str]:
    """Build env dict for pipeline subprocess. If config_dict given use it; else use global _config."""
    env = os.environ.copy()
    with _lock:
        source = _config if config_dict is None else (config_dict or {})
    for k, v in source.items():
        if v:
            env[k] = str(v)
    for key in ("QUALTRICS_API_TOKEN", "GRID_API_TOKEN"):
        if not env.get(key):
            default_val = get_script_default(key)
            if default_val:
                env[key] = default_val
    return env


def get_schedule_params() -> tuple[bool, str, str]:
    """Return (enabled, cron_expr, timezone_str) from global config for scheduler."""
    with _lock:
        return _schedule_params_from(_config)


def get_schedule_params_from_config(config: dict[str, str]) -> tuple[bool, str, str]:
    """Return (enabled, cron_expr, timezone_str) from a config dict (e.g. study config)."""
    return _schedule_params_from(config or {})


def _schedule_params_from(c: dict) -> tuple[bool, str, str]:
    enabled = (c.get("SCHEDULE_ENABLED") or "false").lower() in ("1", "true", "yes")
    cron = (c.get("SCHEDULE_CRON") or "0 9 * * *").strip()
    tz = (c.get("SCHEDULE_TIMEZONE") or "America/Chicago").strip() or "UTC"
    return enabled, cron, tz


def request_stop(study_id: str | None = None) -> tuple[bool, str]:
    """
    Request pipeline stop. If study_id given, only stop when active run is for that study.
    Returns (ok, message). Raises no exception; caller may raise HTTPException on failure.
    """
    global _stop_requested
    with _lock:
        if _status != "running" or _process is None:
            return True, "No run in progress."
        if study_id is not None and _run_study_id != study_id:
            return False, "Run in progress is for another study."
        _stop_requested = True
        proc = _process
    try:
        proc.terminate()
        append_activity("warning", "Stop requested by user.", "stop")
        return True, "Stop requested."
    except Exception as e:
        return False, str(e)


def get_box_config_path(config_dict: dict[str, str] | None = None) -> Path:
    if config_dict is not None:
        p = config_dict.get("BOX_CONFIG_PATH")
    else:
        with _lock:
            p = _config.get("BOX_CONFIG_PATH")
    p = p or ""
    if p and str(p) != "********" and Path(p).exists():
        return Path(p)
    return PROJECT_ROOT / "box.config.json"


def get_grid_token(config_dict: dict[str, str] | None = None) -> str:
    """Grid API token from config_dict, saved config, env, or script default."""
    if config_dict:
        t = config_dict.get("GRID_API_TOKEN")
        if t and t != "********":
            return t
    with _lock:
        t = _config.get("GRID_API_TOKEN")
    if t and t != "********":
        return t
    t = os.environ.get("GRID_API_TOKEN")
    if t:
        return t
    t = get_script_default("GRID_API_TOKEN")
    if t:
        return t
    raise ValueError(
        "Grid API token not set. Set GRID_API_TOKEN in Settings (and save), or set the env var when starting the backend."
    )


def run_pipeline(
    study_id: str | None = None,
    config_dict: dict[str, str] | None = None,
    datastore: "Datastore | None" = None,
    step_order: list[str] | None = None,
    step_types: list[str] | None = None,
) -> None:
    """Start pipeline. If study_id and config_dict given, run for that study. If datastore given, use DB for Box config and processed IDs. step_order (node ids) and step_types (node types in same order) are passed to subprocess as PIPELINE_STEP_ORDER and PIPELINE_STEP_TYPES."""
    global _process, _status, _current_step, _progress_percent, _message, _run_id, _run_study_id, _run_db_id, _datastore_for_logging, _stop_requested
    with _lock:
        _stop_requested = False
        _run_id = str(uuid.uuid4())[:8]
        _run_study_id = study_id
        _status = "running"
        _current_step = "Starting pipeline"
        _progress_percent = 0
        _message = "Pipeline started."
        _activity.clear()
        _run_db_id = None
        _datastore_for_logging = None

    if datastore and study_id:
        try:
            _run_db_id = datastore.create_run(study_id, _run_id)
            _datastore_for_logging = datastore
        except Exception:
            _run_db_id = None
            _datastore_for_logging = None

    append_activity("info", "Pipeline started.", "start")
    env = get_config_for_pipeline(config_dict)
    if step_order:
        env["PIPELINE_STEP_ORDER"] = ",".join(step_order)
    if step_types:
        env["PIPELINE_STEP_TYPES"] = ",".join(step_types)
    # Inject script defaults for tokens when not set (so default tokens load for UI + pipeline)
    for key in ("QUALTRICS_API_TOKEN", "GRID_API_TOKEN"):
        if not env.get(key):
            default_val = get_script_default(key)
            if default_val:
                env[key] = default_val

    temp_paths_to_cleanup: list[str] = []
    processed_ids_path_for_sync: str | None = None
    datastore_for_sync: "Datastore | None" = None
    study_id_for_sync: str | None = None

    if datastore and study_id:
        study_id_for_sync = study_id
        datastore_for_sync = datastore
        box_json = datastore.get_study_box_config(study_id)
        if box_json:
            fd, p = tempfile.mkstemp(suffix=".json")
            try:
                os.write(fd, box_json.encode("utf-8"))
                os.close(fd)
                os.chmod(p, 0o600)
                env["BOX_CONFIG_PATH"] = p
                temp_paths_to_cleanup.append(p)
            except Exception:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                try:
                    os.unlink(p)
                except Exception:
                    pass
                raise
        ids = datastore.get_processed_ids(study_id)
        fd, p = tempfile.mkstemp(suffix=".json")
        try:
            os.write(fd, json.dumps(sorted(ids)).encode("utf-8"))
            os.close(fd)
            os.chmod(p, 0o600)
            env["PROCESSED_IDS_PATH"] = p
            temp_paths_to_cleanup.append(p)
            processed_ids_path_for_sync = p
        except Exception:
            if fd >= 0:
                try:
                    os.close(fd)
                except Exception:
                    pass
                try:
                    os.unlink(p)
                except Exception:
                    pass
                raise

    try:
        proc = subprocess.Popen(
            ["python", str(SCRIPT_PATH)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        for p in temp_paths_to_cleanup:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass
        with _lock:
            _process = None
            _status = "failed"
            _message = str(e)
            run_id_fail = _run_db_id
            store_fail = _datastore_for_logging
            _run_db_id = None
            _datastore_for_logging = None
        append_activity("error", f"Failed to start: {e}", "start")
        if run_id_fail and store_fail:
            try:
                store_fail.update_run(
                    run_id_fail,
                    status="failed",
                    message=str(e)[:65535],
                    finished_at=datetime.now(timezone.utc),
                )
            except Exception:
                pass
        return

    with _lock:
        _process = proc

    def read_stream():
        global _process, _status, _progress_percent, _message
        if proc.stdout is None:
            return
        for line in proc.stdout:
            line = (line or "").strip()
            if not line:
                continue
            level = "info"
            if "Error" in line or "error" in line or "Failed" in line or "Traceback" in line:
                level = "error"
            elif "Warning" in line or "warning" in line or "failed" in line:
                level = "warning"
            elif "Complete" in line or "success" in line.lower():
                level = "success"
            append_activity(level, line)
            with _lock:
                _message = line[:200]
                if "Download" in line or "export" in line.lower():
                    _current_step = "Qualtrics export"
                    _progress_percent = min(25, _progress_percent + 5)
                elif "retrieve" in line.lower() or "videos" in line.lower():
                    _current_step = "Retrieving videos"
                    _progress_percent = min(50, 25 + _progress_percent // 2)
                elif "subject" in line.lower() or "Grid" in line:
                    _current_step = "Grid / subjects"
                    _progress_percent = min(75, 50 + _progress_percent // 2)
                elif "upload" in line.lower() or "Box" in line:
                    _current_step = "Box upload"
                    _progress_percent = min(95, 75 + 10)
        code = proc.poll()
        with _lock:
            _process = None
            _run_study_id = None
            _progress_percent = 100
            if _stop_requested:
                _status = "stopped"
                _message = "Pipeline stopped by user."
            elif code == 0:
                _status = "completed"
                _current_step = "Completed"
                _message = "Pipeline finished successfully."
            else:
                _status = "failed"
                _message = f"Pipeline exited with code {code}."
        append_activity(
            "info" if _status == "completed" else ("warning" if _status == "stopped" else "error"),
            _message,
            "end",
        )
        if processed_ids_path_for_sync and datastore_for_sync and study_id_for_sync:
            try:
                if os.path.exists(processed_ids_path_for_sync):
                    with open(processed_ids_path_for_sync) as f:
                        data = json.load(f)
                    ids_list = data if isinstance(data, list) else (data.get("ids", []) if isinstance(data, dict) else [])
                    if ids_list:
                        datastore_for_sync.add_processed_ids(study_id_for_sync, set(ids_list))
            except Exception:
                pass
        for p in temp_paths_to_cleanup:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass
        run_id_to_update = None
        store_to_update = None
        with _lock:
            run_id_to_update = _run_db_id
            store_to_update = _datastore_for_logging
        if run_id_to_update and store_to_update:
            try:
                store_to_update.update_run(
                    run_id_to_update,
                    status=_status,
                    current_step=_current_step,
                    progress_percent=_progress_percent,
                    message=_message,
                    finished_at=datetime.now(timezone.utc),
                )
            except Exception:
                pass
        with _lock:
            _run_db_id = None
            _datastore_for_logging = None

    t = threading.Thread(target=read_stream)
    t.daemon = True
    t.start()


def list_box_folders(
    root: str,
    config_dict: dict[str, str] | None = None,
    store: "Datastore | None" = None,
    study_id: str | None = None,
) -> dict:
    from boxsdk import Client, JWTAuth

    config_path: Path | None = None
    temp_path: str | None = None
    if store and study_id:
        box_json = store.get_study_box_config(study_id)
        if box_json:
            fd, temp_path = tempfile.mkstemp(suffix=".json")
            try:
                os.write(fd, box_json.encode("utf-8"))
                os.close(fd)
                fd = -1
                os.chmod(temp_path, 0o600)
                config_path = Path(temp_path)
            except Exception:
                if fd >= 0:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
                raise
    if config_path is None:
        config_path = get_box_config_path(config_dict)
    if not config_path or not config_path.exists():
        raise ValueError(
            "Box config not found. Upload Box config in Connections (Box tab) or set BOX_CONFIG_PATH."
        )
    try:
        auth = JWTAuth.from_settings_file(str(config_path))
        client = Client(auth)
        folder = client.folder(root)
        items = folder.get_items(limit=200)
        folders = [{"id": item.id, "name": item.name} for item in items if item.type == "folder"]
        return {"folders": folders}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def list_grid_studies(config_dict: dict[str, str] | None = None) -> dict:
    token = get_grid_token(config_dict)
    url = f"{GRID_BASE_URL}/studies/"
    resp = requests.get(url, headers={"Authorization": token}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    studies = []
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict) and "results" in data:
        raw = data["results"]
    elif isinstance(data, dict) and "studies" in data:
        raw = data["studies"]
    else:
        raw = [data] if isinstance(data, dict) else []
    for s in raw:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("study_id") or s.get("studyId") or str(s.get("pk", ""))
        name = (
            s.get("name") or s.get("study_name") or s.get("studyName") or s.get("title") or str(sid)
        )
        studies.append({"id": str(sid), "name": str(name)})
    return {"studies": studies}
