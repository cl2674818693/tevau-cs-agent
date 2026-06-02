"""Unit tests: config

被测对象：pydantic Settings 默认值 / env 覆盖 / 必填校验 / model_validator / _SettingsProxy.reload。
mock 策略：
- 默认值断言用 `_env_file=None` 关掉本地 .env（开发环境 .env 会污染默认），
  并配合 monkeypatch.delenv 清相关 env，只看类定义的 default。
- env 覆盖用 monkeypatch.setenv（仍 _env_file=None 保证只受 setenv 影响）。
- conftest 已 autouse 设 ANTHROPIC_API_KEY=sk-ant-test 等；测必填缺失时需 delenv。
"""

import pytest
from pydantic import ValidationError

from ai_engine.config import Settings, settings


def _pure_defaults_env(monkeypatch) -> None:
    """剥离所有可能影响"默认值"快照的 env（含 conftest 注入的）。"""
    for var in (
        "ANTHROPIC_BASE_URL",
        "DEFAULT_MODEL",
        "HEAVY_MODEL",
        "SUMMARY_MODEL",
        "DAILY_TOKEN_LIMIT",
        "CHAT_RATE_LIMIT_PER_MIN",
        "MAX_TOOL_DEPTH",
        "MAX_TOOL_RESULT_BYTES",
        "ANTHROPIC_MAX_RETRIES",
        "ANTHROPIC_TIMEOUT_SECONDS",
        "ATTACHMENT_MAX_BYTES",
        "ATTACHMENT_MAX_PER_MESSAGE",
        "ATTACHMENT_URL_TTL_SECONDS",
        "EVENT_CENTER_URL",
        "EVENT_CENTER_SECRET",
        "EVENT_CENTER_SECRET_CURRENT",
        "MOCK_EVENT_CENTER",
        "DEV_TRUST_BU_HEADER",
        "BU_SESSION_SECRET",
        "STAFF_JWT_SECRET",
        "CORS_ALLOW_ORIGINS",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


class TestDefaults:
    """默认值快照（防止误改默认拖垮线上）。
    所有 case 都用 _env_file=None 屏蔽本地 .env，并清干净相关 env。
    """

    def test_default_model_constants(self, monkeypatch) -> None:
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.default_model == "claude-sonnet-4-6"
        assert s.heavy_model == "claude-opus-4-7"
        assert s.summary_model == "claude-haiku-4-5"

    def test_default_limits(self, monkeypatch) -> None:
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.daily_token_limit == 500_000
        assert s.chat_rate_limit_per_min == 30
        assert s.max_tool_depth == 12
        assert s.max_tool_result_bytes == 262_144

    def test_default_anthropic_settings(self, monkeypatch) -> None:
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.anthropic_max_retries == 2
        assert s.anthropic_timeout_seconds == 30.0
        assert s.anthropic_base_url is None

    def test_default_attachment_limits(self, monkeypatch) -> None:
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.attachment_max_bytes == 5 * 1024 * 1024
        assert s.attachment_max_per_message == 4
        assert s.attachment_url_ttl_seconds == 300

    def test_default_event_center_empty(self, monkeypatch) -> None:
        """生产保护：默认空 → 调用方走 Lark 兜底，不静默打不存在的 mock。"""
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.event_center_url == ""
        assert s.event_center_secret_current == ""
        assert s.mock_event_center is False

    def test_default_security_flags(self) -> None:
        """关键防伪造默认值（直接看类 fields，不依赖 env）。"""
        assert Settings.model_fields["dev_trust_bu_header"].default is False
        # secret 默认空（防"空密钥伪造"必须显式配置）
        assert Settings.model_fields["staff_jwt_secret"].default == ""
        assert Settings.model_fields["bu_session_secret"].default == ""

    def test_cors_default_localhost(self, monkeypatch) -> None:
        _pure_defaults_env(monkeypatch)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_allow_origins == ["http://localhost:5173"]


class TestEnvOverrides:
    def test_override_default_model(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("DEFAULT_MODEL", "claude-opus-4-7")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.default_model == "claude-opus-4-7"

    def test_override_int_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1000000")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.daily_token_limit == 1_000_000

    def test_override_float_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("ANTHROPIC_TIMEOUT_SECONDS", "5.5")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.anthropic_timeout_seconds == 5.5

    def test_override_bool_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("MOCK_EVENT_CENTER", "true")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.mock_event_center is True

    def test_override_redis_url(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.redis_url == "redis://localhost:6379/0"

    def test_extra_env_ignored(self, monkeypatch) -> None:
        """Settings 配 extra='ignore'：未声明的 env 不应报错。"""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("TOTALLY_UNUSED_VAR", "x")
        Settings(_env_file=None)  # type: ignore[call-arg]  # 不抛即可


class TestRequiredFields:
    def test_missing_anthropic_api_key_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # 防止 .env 文件兜底（测试目录有时会被读到）
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None)  # type: ignore[call-arg]
        assert "anthropic_api_key" in str(exc.value)


class TestMockEventCenterValidator:
    """_default_mock_event_center_url: 开 mock 且 url 空 → 自动填本地。"""

    def test_auto_fill_when_mock_and_empty(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("MOCK_EVENT_CENTER", "true")
        monkeypatch.delenv("EVENT_CENTER_URL", raising=False)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.event_center_url == "http://localhost:8000/_mock/event-center"

    def test_no_fill_when_mock_off(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("MOCK_EVENT_CENTER", "false")
        monkeypatch.delenv("EVENT_CENTER_URL", raising=False)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.event_center_url == ""

    def test_no_overwrite_when_url_explicitly_set(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("MOCK_EVENT_CENTER", "true")
        monkeypatch.setenv("EVENT_CENTER_URL", "https://prod.example.com/center")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.event_center_url == "https://prod.example.com/center"


class TestSettingsProxy:
    """_SettingsProxy.reload 应刷新单例，新 env 立即可见。"""

    def test_reload_picks_up_new_env(self, monkeypatch) -> None:
        monkeypatch.setenv("DEFAULT_MODEL", "claude-opus-4-7")
        settings.reload()
        assert settings.default_model == "claude-opus-4-7"
        # 改回再 reload
        monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-4-6")
        settings.reload()
        assert settings.default_model == "claude-sonnet-4-6"

    def test_proxy_attr_access_initializes_lazily(self, monkeypatch) -> None:
        """首次访问任意属性都应触发 Settings() 实例化。"""
        # autouse fixture 已经 reload 过；这里只验证读到值。
        v = settings.daily_token_limit
        assert isinstance(v, int) and v > 0

    def test_reload_applies_mock_url_validator(self, monkeypatch) -> None:
        monkeypatch.setenv("MOCK_EVENT_CENTER", "true")
        monkeypatch.delenv("EVENT_CENTER_URL", raising=False)
        settings.reload()
        assert settings.event_center_url == "http://localhost:8000/_mock/event-center"
