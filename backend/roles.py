"""Study and platform role helpers for API (admin vs staff labels, canonical roles)."""

from backend.datastore.base import STUDY_ROLE_ADMIN, STUDY_ROLE_EDITOR, STUDY_ROLE_VIEWER


def normalize_study_role_write(role: str | None) -> str:
    """
    Map API role to canonical datastore role.
    Accepts: admin, staff, editor (staff), viewer (legacy -> upgraded to editor).
    """
    r = (role or "staff").strip().lower()
    if r == "admin":
        return STUDY_ROLE_ADMIN
    if r in ("staff", "editor", "viewer"):
        return STUDY_ROLE_EDITOR
    raise ValueError(f"Invalid study role: {role!r}. Use 'admin' or 'staff'.")


def study_role_label(canonical: str) -> str:
    """Product label: admin | staff (editor and legacy viewer both staff)."""
    if canonical == STUDY_ROLE_ADMIN:
        return "admin"
    return "staff"


def study_role_payload(canonical: str) -> dict:
    """Serialize study role for JSON (label + canonical for clients that need it)."""
    return {
        "role": study_role_label(canonical),
        "roleCanonical": canonical,
    }
