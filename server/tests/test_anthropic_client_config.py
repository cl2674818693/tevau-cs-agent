"""A1: Anthropic 客户端显式 max_retries / timeout（避免 SDK 默认 10min 超时拖死聊天）。"""

import pytest

from ai_engine.config import settings


@pytest.fixture(autouse=True)
def _restore_settings():
    yield
    settings.reload()


def test_client_uses_configured_retries_and_timeout(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_MAX_RETRIES", "5")
    monkeypatch.setenv("ANTHROPIC_TIMEOUT_SECONDS", "12.5")
    settings.reload()

    from ai_engine.integrations import anthropic_client as ac

    client = ac._build_client()
    assert client.max_retries == 5
    assert float(client.timeout) == 12.5


def test_defaults_are_sane(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("ANTHROPIC_MAX_RETRIES", raising=False)
    monkeypatch.delenv("ANTHROPIC_TIMEOUT_SECONDS", raising=False)
    settings.reload()

    # 默认重试 >=2（与 SDK 一致），超时显式且远小于 SDK 默认 600s
    assert settings.anthropic_max_retries >= 2
    assert 0 < settings.anthropic_timeout_seconds <= 60
