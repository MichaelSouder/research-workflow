"""Box and Grid tools: list folders/studies (read-only) and set Box config (dangerous, require confirm)."""

import json

from backend.services import state

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result


def _is_valid_box_config(obj: dict) -> bool:
    if not obj:
        return True
    if "boxAppSettings" in obj and isinstance(obj.get("boxAppSettings"), dict):
        return True
    if "clientID" in obj or "clientId" in obj:
        return True
    return False


def qual_box_folders(study_id: str | None = None, root: str = "0") -> str:
    """
    List Box folders. If study_id is given, use that study's Box config; otherwise use default config.
    root: folder id to list (default '0' for root).
    """
    try:
        store = get_store()
        user = get_user()
        config_dict = None
        if study_id:
            err = require_study_access(store, user, study_id)
            if err:
                return tool_error(err)
            raw = store.get_study_config(study_id)
            config_dict = state.get_study_config_merged(raw)
        result = state.list_box_folders(
            root,
            config_dict=config_dict,
            store=store if study_id else None,
            study_id=study_id,
        )
        return tool_result(result)
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_study_box_config_status(study_id: str) -> str:
    """Return whether Box config is stored for this study (does not return secret content)."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        configured = store.get_study_box_config(study_id) is not None
        return tool_result({"configured": configured})
    except Exception as e:
        return tool_error(str(e))


def qual_grid_studies(study_id: str | None = None) -> str:
    """
    List Grid studies. If study_id is given, use that study's config; otherwise use default.
    """
    try:
        store = get_store()
        user = get_user()
        config_dict = None
        if study_id:
            err = require_study_access(store, user, study_id)
            if err:
                return tool_error(err)
            raw = store.get_study_config(study_id)
            config_dict = state.get_study_config_merged(raw)
        result = state.list_grid_studies(config_dict=config_dict)
        return tool_result(result)
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_box_config_set(
    study_id: str,
    config: dict,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Store Box JWT config for the study. config: full Box config object. Requires confirmation."""
    err = require_confirm("qual_box_config_set", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        raw = config if isinstance(config, dict) else {}
        config_json = json.dumps(raw) if raw else ""
        if config_json and not _is_valid_box_config(raw):
            return tool_error("Invalid Box config: expected JWT config with boxAppSettings or clientID/clientSecret.")
        store.set_study_box_config(study_id, config_json)
        return tool_result({"ok": True, "message": "Box config saved."})
    except Exception as e:
        return tool_error(str(e))
