import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-4-6")
    from ai_engine.config import settings

    settings.reload()
    assert settings.anthropic_api_key == "sk-ant-test"
    assert settings.default_model == "claude-sonnet-4-6"
    assert settings.max_tool_depth == 12


def test_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pydantic import ValidationError

    from ai_engine.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
