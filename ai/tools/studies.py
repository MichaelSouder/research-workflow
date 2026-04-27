"""Study tools: list/get/users (read-only) and create/update/delete/set users (dangerous, require confirm)."""

from backend.datastore.base import STUDY_ROLE_ADMIN

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result


def qual_studies_list() -> str:
    """List all studies the current user has access to, with role (viewer, editor, admin)."""
    try:
        store = get_store()
        user = get_user()
        pairs = store.list_studies_for_user(user.id)
        studies = [
            {"id": s.id, "name": s.name, "description": s.description, "role": role}
            for s, role in pairs
        ]
        return tool_result({"studies": studies})
    except Exception as e:
        return tool_error(str(e))


def qual_study_get(study_id: str) -> str:
    """Get a single study by id. Returns id, name, description, role."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        study = store.get_study(study_id)
        if not study:
            return tool_error("Study not found")
        role = store.get_user_study_role(user.id, study_id)
        return tool_result({
            "id": study.id,
            "name": study.name,
            "description": study.description,
            "role": role,
        })
    except Exception as e:
        return tool_error(str(e))


def qual_study_users_list(study_id: str) -> str:
    """List users and their roles for a study. Requires admin."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id, min_role="admin")
        if err:
            return tool_error(err)
        pairs = store.list_study_users(study_id)
        users = [
            {"id": u.id, "email": u.email, "name": u.name, "role": role}
            for u, role in pairs
        ]
        return tool_result({"users": users})
    except Exception as e:
        return tool_error(str(e))


def qual_study_create(
    name: str,
    description: str | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Create a new study. Caller must be admin of at least one study. Requires confirmation."""
    err = require_confirm("qual_study_create", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        pairs = store.list_studies_for_user(user.id)
        if not any(role == STUDY_ROLE_ADMIN for _, role in pairs):
            return tool_error("Only study admins can create studies.")
        study = store.create_study(
            name=name.strip(),
            description=(description or "").strip() or None,
        )
        store.set_user_study_role(user.id, study.id, STUDY_ROLE_ADMIN)
        return tool_result({"ok": True, "study": {"id": study.id, "name": study.name, "description": study.description}})
    except Exception as e:
        return tool_error(str(e))


def qual_study_update(
    study_id: str,
    name: str | None = None,
    description: str | None = None,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update study name and/or description. Requires admin. Requires confirmation."""
    err = require_confirm("qual_study_update", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="admin")
        if err_acc:
            return tool_error(err_acc)
        if name is None and description is None:
            return tool_result({"ok": True, "message": "Nothing to update."})
        store.update_study(study_id, name=name, description=description)
        return tool_result({"ok": True, "message": "Study updated."})
    except Exception as e:
        return tool_error(str(e))


def qual_study_delete(study_id: str, confirm_dangerous_operation: bool = False) -> str:
    """Delete a study. Requires admin. Fails if a run is in progress. Requires confirmation."""
    err = require_confirm("qual_study_delete", confirm_dangerous_operation)
    if err:
        return err
    try:
        from backend.services import state

        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="admin")
        if err_acc:
            return tool_error(err_acc)
        if state.is_running(study_id):
            return tool_error("Cannot delete study while a pipeline run is in progress. Stop the run first.")
        store.delete_study(study_id)
        return tool_result({"ok": True, "message": "Study deleted."})
    except Exception as e:
        return tool_error(str(e))


def qual_study_users_set(
    study_id: str,
    users: list[dict],
    confirm_dangerous_operation: bool = False,
) -> str:
    """Set user roles for study. users: [{"user_id": "...", "role": "editor"}, ...]. Replaces existing. Requires admin. Requires confirmation."""
    err = require_confirm("qual_study_users_set", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="admin")
        if err_acc:
            return tool_error(err_acc)
        if not isinstance(users, list):
            return tool_error("Body must include 'users' array")
        current = store.list_study_users(study_id)
        for u, _ in current:
            store.remove_user_study(u.id, study_id)
        for item in users:
            uid = item.get("user_id")
            role = (item.get("role") or "viewer").lower()
            if uid and role in ("viewer", "editor", "admin"):
                if store.get_user_by_id(uid):
                    store.set_user_study_role(uid, study_id, role)
        return tool_result({"ok": True, "message": "Users updated."})
    except Exception as e:
        return tool_error(str(e))


def qual_study_user_add(
    study_id: str,
    email: str,
    role: str = "viewer",
    confirm_dangerous_operation: bool = False,
) -> str:
    """Add a user to the study by email. role: viewer, editor, or admin. Requires admin. Requires confirmation."""
    err = require_confirm("qual_study_user_add", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="admin")
        if err_acc:
            return tool_error(err_acc)
        role_l = (role or "viewer").lower()
        if role_l not in ("viewer", "editor", "admin"):
            return tool_error("Role must be viewer, editor, or admin.")
        target = store.get_user_by_email(email)
        if not target:
            return tool_error("No user found with that email.")
        store.set_user_study_role(target.id, study_id, role_l)
        return tool_result({"ok": True, "user": {"id": target.id, "email": target.email, "name": target.name, "role": role_l}})
    except Exception as e:
        return tool_error(str(e))
