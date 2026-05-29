from unittest.mock import MagicMock


async def test_build_request_uses_cached_system(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.integrations.anthropic_client import build_messages_request

    req = build_messages_request(
        system_blocks=[
            {"type": "text", "text": "role+rules (长，需要 cache)"},
            {"type": "text", "text": "examples (长，需要 cache)"},
        ],
        messages=[{"role": "user", "content": "你好"}],
        tools=[{"name": "search_code", "description": "...", "input_schema": {"type": "object"}}],
        model="claude-sonnet-4-6",
    )
    assert all(b.get("cache_control", {}).get("type") == "ephemeral" for b in req["system"])
    assert req["model"] == "claude-sonnet-4-6"
    assert req["tools"][0]["name"] == "search_code"
    assert req["messages"][0]["content"] == "你好"


async def test_build_request_caps_cache_control_at_4(monkeypatch):
    """Anthropic 限制整请求最多 4 个 cache_control 块。游客回合 system 块达 5 个
    （3 基础 + 1 游客约束 + 1 语言兜底），全打缓存会 400。只缓存前 4 个稳定前缀块。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.integrations.anthropic_client import build_messages_request

    blocks = [{"type": "text", "text": f"block-{i}"} for i in range(5)]
    req = build_messages_request(
        system_blocks=blocks, messages=[], tools=None, model="claude-sonnet-4-6"
    )
    cached = [b for b in req["system"] if "cache_control" in b]
    assert len(cached) <= 4
    assert len(req["system"]) == 5  # 所有块仍原样下发，只是后面的不打缓存断点
    assert all("cache_control" in b for b in req["system"][:4])
    assert "cache_control" not in req["system"][4]


async def test_stream_turn_yields_deltas_then_final(monkeypatch):
    """stream_turn 先逐段 yield 文本增量，最后 yield 完整消息（final）。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.integrations import anthropic_client as ac

    final_msg = MagicMock(content=[MagicMock(type="text", text="你好")], stop_reason="end_turn")

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def text_stream(self):
            async def _gen():
                for piece in ("你", "好"):
                    yield piece

            return _gen()

        async def get_final_message(self):
            return final_msg

    fake_client = MagicMock()
    fake_client.messages.stream = MagicMock(return_value=FakeStream())
    monkeypatch.setattr(ac, "_client", fake_client)

    deltas, final = [], None
    async for chunk in ac.stream_turn({"model": "x", "system": [], "messages": []}):
        if "final" in chunk:
            final = chunk["final"]
        else:
            deltas.append(chunk["text_delta"])
    assert "".join(deltas) == "你好"
    assert final is final_msg
