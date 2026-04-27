"""Status and activity tools: global and study-scoped."""

from backend.services import state

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, tool_error, tool_result


def qual_status(study_id: str | None = None) -> str:
    """Get run status. If study_id is given, returns status only when active run is for that study."""
    try:
        if study_id:
            store = get_store()
            user = get_user()
            err = require_study_access(store, user, study_id)
            if err:
                return tool_error(err)
        return tool_result(state.get_status(study_id))
    except Exception as e:
        return tool_error(str(e))


def qual_study_status(study_id: str) -> str:
    """Get run status for a specific study."""
    return qual_status(study_id)


def qual_activity(study_id: str | None = None) -> str:
    """Get activity log. If study_id given, returns activity only when active run is for that study."""
    try:
        if study_id:
            store = get_store()
            user = get_user()
            err = require_study_access(store, user, study_id)
            if err:
                return tool_error(err)
        return tool_result(state.get_activity(study_id))
    except Exception as e:
        return tool_error(str(e))


def qual_study_activity(study_id: str) -> str:
    """Get activity log for a specific study."""
    return qual_activity(study_id)


def qual_study_errors(study_id: str) -> str:
    """Get errors (and warnings) from the activity log for a study."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        return tool_result(state.get_errors(study_id))
    except Exception as e:
        return tool_error(str(e))
