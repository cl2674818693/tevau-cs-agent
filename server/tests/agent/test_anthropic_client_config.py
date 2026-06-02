"""Anthropic client config: base_url / max_retries / timeout / api_key

被测对象：integrations.anthropic_client._build_client
- 默认 base_url=None（SDK 用官方端点）。
- 显式 base_url 配置 → 透传到 AsyncAnthropic。
- max_retries / timeout 来自 settings；显式收紧避免默认 600s。
- api_key 必填（pydantic settings 校验）。
- build_messages_request 缓存断点常量 _MAX_CACHE_BLOCKS=4 与现实 Anthropic 限制对齐。
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_engine.integrations import anthropic_client as ac


class TestBuildClient:
    """_build_client 把 settings 中的字段传给 AsyncAnthropic。"""

    def test_default_base_url_is_none(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "anthropic_base_url", None)
        monkeypatch.setattr(_settings, "anthropic_max_retries", 2)
        monkeypatch.setattr(_settings, "anthropic_timeout_seconds", 30.0)
        with patch.object(ac, "AsyncAnthropic", autospec=True) as mocked:
            ac._build_client()
            kwargs = mocked.call_args.kwargs
            assert kwargs["base_url"] is None
            assert kwargs["max_retries"] == 2
            assert kwargs["timeout"] == 30.0

    def test_custom_base_url_passthrough(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "anthropic_base_url", "https://gw.internal")
        with patch.object(ac, "AsyncAnthropic", autospec=True) as mocked:
            ac._build_client()
            assert mocked.call_args.kwargs["base_url"] == "https://gw.internal"

    def test_max_retries_from_settings(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "anthropic_max_retries", 5)
        with patch.object(ac, "AsyncAnthropic", autospec=True) as mocked:
            ac._build_client()
            assert mocked.call_args.kwargs["max_retries"] == 5

    def test_timeout_from_settings(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "anthropic_timeout_seconds", 12.5)
        with patch.object(ac, "AsyncAnthropic", autospec=True) as mocked:
            ac._build_client()
            assert mocked.call_args.kwargs["timeout"] == 12.5

    def test_api_key_passed(self, monkeypatch) -> None:
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "anthropic_api_key", "sk-ant-secret")
        with patch.object(ac, "AsyncAnthropic", autospec=True) as mocked:
            ac._build_client()
            assert mocked.call_args.kwargs["api_key"] == "sk-ant-secret"


class TestModuleClient:
    """模块顶部 _client 在 import 时已被初始化（生产期单例）。"""

    def test_client_is_singleton(self) -> None:
        assert ac._client is not None
        # 多次访问同一实例
        assert ac._client is ac._client


class TestCacheConstant:
    def test_max_cache_blocks_is_four(self) -> None:
        # Anthropic 当前限制：单请求最多 4 个 cache_control 块
        assert ac._MAX_CACHE_BLOCKS == 4


class TestBuildMessagesRequestStructural:
    """build_messages_request 结构性检查：max_tokens 默认 4096；tools None→[]。"""

    def test_default_max_tokens(self) -> None:
        req = ac.build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m"
        )
        assert req["max_tokens"] == 4096

    def test_tools_none_becomes_empty_list(self) -> None:
        req = ac.build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m"
        )
        assert req["tools"] == []

    def test_does_not_mutate_input(self) -> None:
        blocks = [{"type": "text", "text": "a"}]
        ac.build_messages_request(
            system_blocks=blocks, messages=[], tools=None, model="m"
        )
        # 入参未被回写 cache_control
        assert "cache_control" not in blocks[0]


class TestClassifyTopicCallShape:
    """classify_topic 用 messages.create，传 system + 单条 user message + 固定 max_tokens=10。"""

    async def test_call_kwargs(self, monkeypatch) -> None:
        from types import SimpleNamespace

        captured: dict = {}

        async def _create(**kw):
            captured.update(kw)
            return SimpleNamespace(content=[SimpleNamespace(text="yes")])

        # 用 MagicMock 包装让 monkeypatch 生效
        mock = MagicMock(side_effect=_create)
        monkeypatch.setattr(ac._client.messages, "create", mock)
        await ac.classify_topic("查余额")
        assert captured["max_tokens"] == 10
        assert captured["stop_sequences"] == ["\n"]
        assert captured["messages"] == [{"role": "user", "content": "查余额"}]


class TestStreamTurnShape:
    """stream_turn 把 request_body 透传给 _client.messages.stream。"""

    async def test_passes_request_body_through(self, monkeypatch, fake_stream) -> None:
        captured: list[dict] = []
        from types import SimpleNamespace

        final_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="x")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )

        def _wrap(**kw):  # noqa: ANN003
            captured.append(kw)
            # delegate 到 fake_stream
            return fake_stream(final_resp)(**kw)

        monkeypatch.setattr(ac._client.messages, "stream", _wrap)
        async for _ in ac.stream_turn({"model": "m", "messages": [], "system": [], "tools": []}):
            pass
        assert captured and captured[0]["model"] == "m"


class TestApiKeyMissingFails:
    """settings ANTHROPIC_API_KEY 缺失时 Settings 构造应抛错（pydantic ValidationError）。

    注意：pydantic-settings 同时读 env 和 .env 文件；本地 dev 通常 .env 里有 ANTHROPIC_API_KEY，
    需要 patch model_config 关闭 env_file 才能验证"纯环境变量"路径。
    """

    def test_missing_api_key_raises(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from ai_engine.config import Settings

        # 切到一个不存在 .env 的临时目录
        monkeypatch.chdir(tmp_path)
        # 同时 patch class 的 model_config，禁用 env_file 回退
        from pydantic_settings import SettingsConfigDict

        monkeypatch.setattr(
            Settings,
            "model_config",
            SettingsConfigDict(env_file=None, env_file_encoding="utf-8", extra="ignore"),
        )

        with pytest.raises(Exception):  # pydantic.ValidationError
            Settings()  # type: ignore[call-arg]
