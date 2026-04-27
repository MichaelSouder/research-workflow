"""
One-time migration: create default study from ui_config.json and assign existing users.
Called from app lifespan when no studies exist.
"""

import json
from pathlib import Path

from backend.datastore.base import Datastore, STUDY_ROLE_EDITOR


def ensure_default_study(store: Datastore, config_file: Path) -> None:
    """
    If no studies exist: create "Default" study, copy config from config_file
    into study config, and assign all existing users as editor.
    """
    if store.has_any_study():
        return
    study = store.create_study("Default", description="Default pipeline (migrated from global config)")
    config: dict[str, str] = {}
    if config_file.exists():
        try:
            with open(config_file) as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                config = {k: str(v) for k, v in raw.items() if v is not None}
        except Exception:
            pass
    store.set_study_config(study.id, config)
    for user in store.list_users():
        store.set_user_study_role(user.id, study.id, STUDY_ROLE_EDITOR)
