"""Resolve MCP user for in-process mode: create or get mcp-bot@local and ensure admin on all studies."""

from backend.datastore import get_datastore
from backend.datastore.base import STUDY_ROLE_ADMIN, User


MCP_GOOGLE_ID = "mcp-bot-local"
MCP_EMAIL = "mcp-bot@local"
MCP_NAME = "MCP Bot"


def get_mcp_user(store=None) -> User:
    """
    Return the MCP service user, creating it if needed.
    Ensures the user has admin access to every study (so all tools can run).
    """
    if store is None:
        store = get_datastore()
    user = store.create_or_update_user(google_id=MCP_GOOGLE_ID, email=MCP_EMAIL, name=MCP_NAME)
    for study in store.list_all_studies():
        store.set_user_study_role(user.id, study.id, STUDY_ROLE_ADMIN)
    return user
