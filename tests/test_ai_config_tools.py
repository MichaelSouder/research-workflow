import json

from ai.tools import config as config_tools


class _User:
    def __init__(self, user_id: str):
        self.id = user_id


class _Study:
    def __init__(self, study_id: str):
        self.id = study_id


class _Store:
    def __init__(self, study_ids: list[str]):
        self._study_ids = study_ids

    def list_studies_for_user(self, _user_id: str):
        return [(_Study(sid), "admin") for sid in self._study_ids]


def test_qual_config_get_rejects_ambiguous_multi_study(monkeypatch):
    monkeypatch.setattr(config_tools, "get_store", lambda: _Store(["s1", "s2"]))
    monkeypatch.setattr(config_tools, "get_user", lambda: _User("u1"))
    result = json.loads(config_tools.qual_config_get())
    assert "error" in result
    assert "ambiguous" in result["error"].lower()
    assert "qual_study_config_get" in result["error"]


def test_qual_config_set_rejects_ambiguous_multi_study(monkeypatch):
    monkeypatch.setattr(config_tools, "get_store", lambda: _Store(["s1", "s2"]))
    monkeypatch.setattr(config_tools, "get_user", lambda: _User("u1"))
    result = json.loads(
        config_tools.qual_config_set(
            {"GRID_STUDY_ID": "999"},
            confirm_dangerous_operation=True,
        )
    )
    assert "error" in result
    assert "ambiguous" in result["error"].lower()
    assert "qual_study_config_set" in result["error"]
