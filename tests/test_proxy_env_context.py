"""Per-request data proxy override for HTTP tool API."""

from ai.proxy_env import PROXY_ENABLED_ENV, data_proxy_request_context, is_proxy_enabled


def test_is_proxy_reads_env_when_no_context(monkeypatch):
    monkeypatch.delenv(PROXY_ENABLED_ENV, raising=False)
    assert is_proxy_enabled() is False
    monkeypatch.setenv(PROXY_ENABLED_ENV, "1")
    assert is_proxy_enabled() is True


def test_request_context_overrides_env(monkeypatch):
    monkeypatch.setenv(PROXY_ENABLED_ENV, "0")
    assert is_proxy_enabled() is False
    with data_proxy_request_context(True):
        assert is_proxy_enabled() is True
    assert is_proxy_enabled() is False


def test_request_context_can_disable_despite_env(monkeypatch):
    monkeypatch.setenv(PROXY_ENABLED_ENV, "1")
    assert is_proxy_enabled() is True
    with data_proxy_request_context(False):
        assert is_proxy_enabled() is False
    assert is_proxy_enabled() is True
