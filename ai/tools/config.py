"""Config tools: get (read-only) and set (dangerous, require confirm)."""

import os

from backend.services import state

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result

MCP_REVEAL_SECRETS_ENV = "MCP_REVEAL_SECRETS"


def _allow_reveal_secrets(reveal_secrets: bool) -> bool:
    """Only allow revealing secrets if MCP_REVEAL_SECRETS=1."""
    if not reveal_secrets:
        return False
    return (os.environ.get(MCP_REVEAL_SECRETS_ENV) or "").strip().lower() in ("1", "true", "yes")


def qual_study_config_get(study_id: str, reveal_secrets: bool = False) -> str:
    """Get study config (keys and values). Secrets are masked unless reveal_secrets is true and MCP_REVEAL_SECRETS=1."""
    try:
        reveal = _allow_reveal_secrets(reveal_secrets)
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        raw = store.get_study_config(study_id)
        result = state.get_merged_config_from_study_config(raw, reveal_secrets=reveal)
        return tool_result(result)
    except Exception as e:
        return tool_error(str(e))


def qual_config_get(reveal_secrets: bool = False) -> str:
    """Get merged config for a single-study user (legacy). Secrets masked unless reveal_secrets and MCP_REVEAL_SECRETS=1."""
    try:
        reveal = _allow_reveal_secrets(reveal_secrets)
        store = get_store()
        user = get_user()
        pairs = store.list_studies_for_user(user.id)
        if len(pairs) > 1:
            return tool_error(
                "Legacy qual_config_get is ambiguous for users with multiple studies. "
                "Use qual_study_config_get(study_id=...) instead."
            )
        if not pairs:
            return tool_result(state.get_merged_config(reveal_secrets=reveal))
        study_id = pairs[0][0].id
        raw = store.get_study_config(study_id)
        result = state.get_merged_config_from_study_config(raw, reveal_secrets=reveal)
        return tool_result(result)
    except Exception as e:
        return tool_error(str(e))


def qual_study_config_set(
    study_id: str,
    config: dict,
    persist: bool = True,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update config for a study. config: key-value dict. Requires editor. Requires confirmation."""
    err = require_confirm("qual_study_config_set", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if not isinstance(config, dict):
            return tool_error("config must be an object")
        store.set_study_config(study_id, {k: str(v) for k, v in config.items() if v is not None})
        from backend.services import scheduler as scheduler_service
        scheduler_service.refresh_schedule()
        return tool_result({"ok": True, "message": "Config updated." + (" Saved." if persist else "")})
    except Exception as e:
        return tool_error(str(e))


def qual_config_set(
    config: dict,
    persist: bool = True,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update config for a single-study user (legacy). Requires confirmation."""
    err = require_confirm("qual_config_set", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        pairs = store.list_studies_for_user(user.id)
        from backend.services import scheduler as scheduler_service
        if len(pairs) > 1:
            return tool_error(
                "Legacy qual_config_set is ambiguous for users with multiple studies. "
                "Use qual_study_config_set(study_id=..., config=...) instead."
            )
        if not pairs:
            state.update_config(config if isinstance(config, dict) else {}, persist=False)
            scheduler_service.refresh_schedule()
            return tool_result({"ok": True, "message": "Config updated (no study; in-memory only)."})
        study_id = pairs[0][0].id
        current = store.get_study_config(study_id)
        merged = {**current, **{k: str(v) for k, v in (config or {}).items() if v not in (None, "", "********")}}
        store.set_study_config(study_id, merged)
        scheduler_service.refresh_schedule()
        return tool_result({"ok": True, "message": "Config updated."})
    except Exception as e:
        return tool_error(str(e))
