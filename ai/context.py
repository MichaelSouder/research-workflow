"""Process-global context for MCP: datastore and MCP user. Set at startup in __main__."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.datastore.base import Datastore, User

_store: "Datastore | None" = None
_user: "User | None" = None


def set_context(store: "Datastore", user: "User") -> None:
    global _store, _user
    _store = store
    _user = user


def get_store() -> "Datastore":
    if _store is None:
        raise RuntimeError("MCP context not initialized; run python -m ai after app is configured.")
    return _store


def get_user() -> "User":
    if _user is None:
        raise RuntimeError("MCP context not initialized; run python -m ai after app is configured.")
    return _user
