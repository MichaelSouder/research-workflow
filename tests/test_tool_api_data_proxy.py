"""HTTP /v1/tools/invoke respects per-owner tool_api_data_proxy_enabled."""

import pytest
from fastapi.testclient import TestClient

from backend.datastore.mock import MockDatastore
from backend.main import app
from backend.routers.auth import get_current_user


def test_integrations_ping_unauthenticated(memory_store, monkeypatch):
    monkeypatch.setattr("backend.main.get_datastore", lambda: memory_store)
    with TestClient(app) as client:
        r = client.get("/api/integrations/ping")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "integrations": True}


def test_integrations_mcp_keys_lists_owner_and_viewer_id(memory_store, monkeypatch):
    owner = memory_store.create_or_update_user("google-int", "int@t.example", "Int")
    other = memory_store.create_or_update_user("google-oth", "oth@t.example", "Oth")
    sid = memory_store.list_all_studies()[0].id
    memory_store.create_mcp_api_key("mine", [], owner_user_id=owner.id, allowed_study_ids=[sid])
    memory_store.create_mcp_api_key("theirs", [], owner_user_id=other.id, allowed_study_ids=[sid])

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            r = client.get("/api/integrations/mcp-api-keys")
        assert r.status_code == 200
        body = r.json()
        assert body["viewerUserId"] == owner.id
        assert len(body["keys"]) == 1
        assert body["keys"][0]["name"] == "mine"
        assert body.get("ownedButInactive") == []
        assert "activeKeysNotOwnedByYou" not in body
        assert "inactiveKeysNotOwnedByYou" not in body
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_integrations_mcp_keys_reports_owned_expired(memory_store, monkeypatch):
    from datetime import datetime, timedelta, timezone

    owner = memory_store.create_or_update_user("google-exp", "exp@t.example", "Exp")
    sid = memory_store.list_all_studies()[0].id
    past = datetime.now(timezone.utc) - timedelta(days=1)
    memory_store.create_mcp_api_key(
        "old", [], owner_user_id=owner.id, allowed_study_ids=[sid], expires_at=past
    )

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            r = client.get("/api/integrations/mcp-api-keys")
        assert r.status_code == 200
        body = r.json()
        assert body["keys"] == []
        assert len(body["ownedButInactive"]) == 1
        assert body["ownedButInactive"][0]["name"] == "old"
        assert body["ownedButInactive"][0]["reason"] == "expired"
        assert "inactiveKeysNotOwnedByYou" not in body
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_integrations_mcp_keys_superuser_sees_other_owner_keys(memory_store, monkeypatch):
    su = memory_store.create_or_update_user("google-su", "su@t.example", "SU")
    memory_store.set_user_superuser(su.id, True)
    other = memory_store.create_or_update_user("google-oth2", "oth2@t.example", "Oth2")
    sid = memory_store.list_all_studies()[0].id
    memory_store.create_mcp_api_key("notmine", [], owner_user_id=other.id, allowed_study_ids=[sid])

    app.dependency_overrides[get_current_user] = lambda: memory_store.get_user_by_id(su.id)
    try:
        with TestClient(app) as client:
            r = client.get("/api/integrations/mcp-api-keys")
        assert r.status_code == 200
        body = r.json()
        assert body["keys"] == []
        hint = body["activeKeysNotOwnedByYou"]
        assert len(hint) == 1
        assert hint[0]["name"] == "notmine"
        assert hint[0]["ownerUserId"] == other.id
        assert body.get("ownedButInactive") == []
        assert body.get("inactiveKeysNotOwnedByYou") == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_integrations_superuser_sees_inactive_key_owned_by_other(memory_store, monkeypatch):
    from datetime import datetime, timedelta, timezone

    su = memory_store.create_or_update_user("google-su3", "su3@t.example", "SU3")
    memory_store.set_user_superuser(su.id, True)
    other = memory_store.create_or_update_user("google-oth3", "oth3@t.example", "Oth3")
    sid = memory_store.list_all_studies()[0].id
    past = datetime.now(timezone.utc) - timedelta(days=1)
    memory_store.create_mcp_api_key(
        "dead", [], owner_user_id=other.id, allowed_study_ids=[sid], expires_at=past
    )

    app.dependency_overrides[get_current_user] = lambda: memory_store.get_user_by_id(su.id)
    try:
        with TestClient(app) as client:
            r = client.get("/api/integrations/mcp-api-keys")
        assert r.status_code == 200
        body = r.json()
        assert body["keys"] == []
        assert body["activeKeysNotOwnedByYou"] == []
        hint = body["inactiveKeysNotOwnedByYou"]
        assert len(hint) == 1
        assert hint[0]["name"] == "dead"
        assert hint[0]["reason"] == "expired"
        assert hint[0]["ownerUserId"] == other.id
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def memory_store(monkeypatch):
    store = MockDatastore()
    store.create_study("Test Study", "integration tests")
    # Lifespan uses main.get_datastore; patch both module entry points.
    monkeypatch.setattr("backend.main.get_datastore", lambda: store)
    monkeypatch.setattr("backend.datastore.get_datastore", lambda: store)
    return store


def test_tool_invoke_proxies_for_db_key_when_owner_proxy_on(memory_store, monkeypatch):
    monkeypatch.delenv("MCP_DATA_PROXY_ENABLED", raising=False)
    owner = memory_store.create_or_update_user("google-owner", "owner@t.example", "Owner")
    memory_store.set_user_tool_api_data_proxy(owner.id, True)
    sid = memory_store.list_all_studies()[0].id
    _rec, secret = memory_store.create_mcp_api_key(
        "k1", [], owner_user_id=owner.id, allowed_study_ids=[sid]
    )

    with TestClient(app) as client:
        r = client.post(
            "/v1/tools/invoke",
            headers={"Authorization": f"Bearer {secret}"},
            json={"tool": "qual_studies_list", "arguments": {"study_id": sid}},
        )
    assert r.status_code == 200
    body = r.json()
    studies = body.get("studies") if isinstance(body, dict) else None
    assert isinstance(studies, list) and studies
    # Proxied response uses synthetic study ids, not the real default study id.
    assert all(s.get("id") != sid for s in studies if isinstance(s, dict))


def test_tool_invoke_no_proxy_when_owner_flag_off(memory_store, monkeypatch):
    monkeypatch.delenv("MCP_DATA_PROXY_ENABLED", raising=False)
    owner = memory_store.create_or_update_user("google-owner2", "owner2@t.example", "Owner2")
    memory_store.set_user_tool_api_data_proxy(owner.id, False)
    sid = memory_store.list_all_studies()[0].id
    _rec, secret = memory_store.create_mcp_api_key(
        "k2", [], owner_user_id=owner.id, allowed_study_ids=[sid]
    )

    with TestClient(app) as client:
        r = client.post(
            "/v1/tools/invoke",
            headers={"Authorization": f"Bearer {secret}"},
            json={"tool": "qual_studies_list", "arguments": {"study_id": sid}},
        )
    assert r.status_code == 200
    body = r.json()
    studies = body.get("studies") if isinstance(body, dict) else None
    assert isinstance(studies, list) and studies
    ids = [s.get("id") for s in studies if isinstance(s, dict)]
    assert sid in ids


def test_integration_bundle_rejects_wrong_secret(memory_store, monkeypatch):
    owner = memory_store.create_or_update_user("google-b", "b@t.example", "B")
    sid = memory_store.list_all_studies()[0].id
    rec, secret = memory_store.create_mcp_api_key(
        "kb", [], owner_user_id=owner.id, allowed_study_ids=[sid]
    )

    app.dependency_overrides[get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/integrations/bundles/claude",
                json={"api_key_id": rec.id, "api_key_secret": "wrong-secret"},
            )
        assert r.status_code == 403

        with TestClient(app) as client:
            r_ok = client.post(
                "/api/integrations/bundles/claude",
                json={"api_key_id": rec.id, "api_key_secret": secret},
            )
        assert r_ok.status_code == 200
        assert r_ok.headers.get("content-type", "").startswith("application/zip")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
