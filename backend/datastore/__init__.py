"""Datastore abstraction: mock (dev) or MariaDB (production)."""

import os

from backend.datastore.base import (
    Datastore,
    Session,
    Study,
    User,
    UserStudy,
    STUDY_ROLE_ADMIN,
    STUDY_ROLE_EDITOR,
    STUDY_ROLE_VIEWER,
)
from backend.datastore.mock import MockDatastore


def get_datastore() -> Datastore:
    """
    Return datastore implementation based on env.
    DATASTORE=memory (default) -> MockDatastore.
    DATASTORE=mariadb -> MariaDB (requires DATABASE_URL).
    """
    kind = (os.environ.get("DATASTORE") or "memory").strip().lower()
    if kind == "mariadb":
        from backend.datastore.mariadb import MariaDBDatastore

        url = os.environ.get("DATABASE_URL")
        if not url:
            raise ValueError("DATASTORE=mariadb requires DATABASE_URL")
        return MariaDBDatastore(url)
    return MockDatastore()


__all__ = [
    "Datastore",
    "Session",
    "Study",
    "User",
    "UserStudy",
    "STUDY_ROLE_ADMIN",
    "STUDY_ROLE_EDITOR",
    "STUDY_ROLE_VIEWER",
    "MockDatastore",
    "get_datastore",
]
