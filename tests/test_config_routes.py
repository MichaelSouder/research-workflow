from fastapi import HTTPException

from backend.routers.config_routes import _resolve_legacy_study_id


class _Study:
    def __init__(self, study_id: str):
        self.id = study_id


class _Store:
    def __init__(self, study_ids: list[str]):
        self._study_ids = study_ids

    def list_studies_for_user(self, _user_id: str):
        return [(_Study(sid), "admin") for sid in self._study_ids]


def test_resolve_legacy_study_id_none_when_no_studies():
    store = _Store([])
    assert _resolve_legacy_study_id(store, "u1") is None


def test_resolve_legacy_study_id_returns_only_study():
    store = _Store(["study-a"])
    assert _resolve_legacy_study_id(store, "u1") == "study-a"


def test_resolve_legacy_study_id_rejects_multiple_studies():
    store = _Store(["study-a", "study-b"])
    try:
        _resolve_legacy_study_id(store, "u1")
        assert False, "Expected HTTPException for ambiguous legacy config route"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "Use /api/studies/{study_id}/config instead." in str(exc.detail)
