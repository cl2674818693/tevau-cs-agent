"""Unit tests: integrations.anthropic_client

被测对象：build_messages_request 缓存断点分配 + classify_topic 解析 + stream_turn 流式。
mock 策略：
- build_messages_request 是纯函数，直接断言结构。
- classify_topic 用 MagicMock 替换 `_client.messages.create`（async）。
- stream_turn 用 conftest 的 fake_stream fixture 替换 `_client.messages.stream`。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai_engine.integrations import anthropic_client as ac


class TestBuildMessagesRequest:
    """前 _MAX_CACHE_BLOCKS=4 个 system 块加 cache_control，其余原样。"""

    def _blocks(self, n: int) -> list[dict[str, str]]:
        return [{"type": "text", "text": f"b{i}"} for i in range(n)]

    def test_zero_blocks(self) -> None:
        req = ac.build_messages_request(
            system_blocks=[], messages=[{"role": "user", "content": "hi"}],
            tools=None, model="m",
        )
        assert req["system"] == []
        assert req["tools"] == []
        assert req["max_tokens"] == 4096
        assert req["model"] == "m"

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_one_to_four_blocks_all_cached(self, n: int) -> None:
        req = ac.build_messages_request(
            system_blocks=self._blocks(n), messages=[], tools=None, model="m",
        )
        for blk in req["system"]:
            assert blk["cache_control"] == {"type": "ephemeral"}
        assert len(req["system"]) == n

    def test_five_blocks_only_first_four_cached(self) -> None:
        req = ac.build_messages_request(
            system_blocks=self._blocks(5), messages=[], tools=None, model="m",
        )
        assert all("cache_control" in b for b in req["system"][:4])
        assert "cache_control" not in req["system"][4]

    def test_six_blocks_only_first_four_cached(self) -> None:
        req = ac.build_messages_request(
            system_blocks=self._blocks(6), messages=[], tools=None, model="m",
        )
        assert sum(1 for b in req["system"] if "cache_control" in b) == 4
        assert sum(1 for b in req["system"] if "cache_control" not in b) == 2

    def test_tools_none_becomes_empty_list(self) -> None:
        req = ac.build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m",
        )
        assert req["tools"] == []

    def test_tools_passthrough(self) -> None:
        tools = [{"name": "t1"}, {"name": "t2"}]
        req = ac.build_messages_request(
            system_blocks=[], messages=[], tools=tools, model="m",
        )
        assert req["tools"] == tools

    def test_custom_max_tokens(self) -> None:
        req = ac.build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m", max_tokens=128,
        )
        assert req["max_tokens"] == 128

    def test_does_not_mutate_input_blocks(self) -> None:
        """build 返回新 dict，不应回写入参（避免反复调用累积 cache_control）。"""
        blocks = self._blocks(2)
        ac.build_messages_request(
            system_blocks=blocks, messages=[], tools=None, model="m",
        )
        for b in blocks:
            assert "cache_control" not in b


class TestClassifyTopic:
    """模型多 content block 拼接 + strip + lower。"""

    async def test_single_block(self, monkeypatch) -> None:
        resp = SimpleNamespace(content=[SimpleNamespace(text="YES")])
        mock_create = AsyncMock(return_value=resp)
        monkeypatch.setattr(ac._client.messages, "create", mock_create)

        out = await ac.classify_topic("查余额")
        assert out == "yes"
        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == ac.settings.summary_model
        assert call_kwargs["max_tokens"] == 10
        assert call_kwargs["stop_sequences"] == ["\n"]
        assert call_kwargs["system"] == ac._CLASSIFY_SYSTEM
        assert call_kwargs["messages"] == [{"role": "user", "content": "查余额"}]

    async def test_multi_blocks_concatenated(self, monkeypatch) -> None:
        resp = SimpleNamespace(
            content=[
                SimpleNamespace(text="un"),
                SimpleNamespace(text="cer"),
                SimpleNamespace(text="tain"),
            ]
        )
        monkeypatch.setattr(ac._client.messages, "create", AsyncMock(return_value=resp))
        assert await ac.classify_topic("?") == "uncertain"

    async def test_block_without_text_attr_skipped(self, monkeypatch) -> None:
        """getattr(b, 'text', '') 对没有 text 的 block 兜底为 ''。"""
        resp = SimpleNamespace(
            content=[
                SimpleNamespace(text="yes"),
                SimpleNamespace(type="tool_use"),  # 没有 text
            ]
        )
        monkeypatch.setattr(ac._client.messages, "create", AsyncMock(return_value=resp))
        assert await ac.classify_topic("hi") == "yes"

    async def test_empty_content_returns_empty(self, monkeypatch) -> None:
        resp = SimpleNamespace(content=[])
        monkeypatch.setattr(ac._client.messages, "create", AsyncMock(return_value=resp))
        assert await ac.classify_topic("hi") == ""

    async def test_upstream_failure_propagates(self, monkeypatch) -> None:
        async def _boom(**_k: object) -> object:
            raise RuntimeError("api down")

        monkeypatch.setattr(ac._client.messages, "create", _boom)
        with pytest.raises(RuntimeError, match="api down"):
            await ac.classify_topic("hi")


class TestStreamTurn:
    """stream_turn 应 yield 全部 text_delta + 一个 final。"""

    async def test_yields_text_then_final(self, monkeypatch, fake_stream) -> None:
        final_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello world")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=2),
        )
        monkeypatch.setattr(ac._client.messages, "stream", fake_stream(final_resp))

        chunks: list[dict[str, object]] = []
        async for ev in ac.stream_turn(
            {"model": "m", "system": [], "messages": [], "tools": [], "max_tokens": 4}
        ):
            chunks.append(ev)
        # 至少 1 个 text_delta + 末尾 1 个 final
        assert chunks[-1] == {"final": final_resp}
        text_deltas = [c["text_delta"] for c in chunks if "text_delta" in c]
        assert "".join(text_deltas) == "hello world"

    async def test_multi_text_blocks(self, monkeypatch, fake_stream) -> None:
        final_resp = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="part1 "),
                SimpleNamespace(type="text", text="part2"),
            ],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=5, output_tokens=3),
        )
        monkeypatch.setattr(ac._client.messages, "stream", fake_stream(final_resp))

        text = ""
        final = None
        async for ev in ac.stream_turn({"model": "m"}):
            if "text_delta" in ev:
                text += ev["text_delta"]
            elif "final" in ev:
                final = ev["final"]
        assert text == "part1 part2"
        assert final is final_resp

    async def test_tool_use_block_skipped_in_text_stream(
        self, monkeypatch, fake_stream
    ) -> None:
        """非 text 类型的 content block 不应进 text_stream（fake_stream 模拟此行为）。"""
        final_resp = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="ok"),
                SimpleNamespace(type="tool_use", name="q"),
            ],
            stop_reason="tool_use",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )
        monkeypatch.setattr(ac._client.messages, "stream", fake_stream(final_resp))

        events = [e async for e in ac.stream_turn({"model": "m"})]
        text_deltas = [e["text_delta"] for e in events if "text_delta" in e]
        assert text_deltas == ["ok"]
        assert events[-1]["final"] is final_resp


class TestMaxCacheBlocksConstant:
    def test_constant_is_four(self) -> None:
        """Anthropic 当前限制：单请求最多 4 个 cache_control 块。"""
        assert ac._MAX_CACHE_BLOCKS == 4
