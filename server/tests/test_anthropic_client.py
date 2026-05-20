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


async def test_stream_yields_text_deltas(monkeypatch):
    """烟雾测试：stream 函数能 yield 文本增量。用 mock Anthropic 客户端。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.integrations import anthropic_client as ac

    fake_events = [
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="你")),
        MagicMock(type="content_block_delta", delta=MagicMock(type="text_delta", text="好")),
        MagicMock(type="message_stop"),
    ]

    class FakeStream:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def __aiter__(self):
            for ev in fake_events:
                yield ev

    fake_client = MagicMock()
    fake_client.messages.stream = MagicMock(return_value=FakeStream())
    monkeypatch.setattr(ac, "_client", fake_client)

    out = []
    async for chunk in ac.stream_text_only({"model": "x", "system": [], "messages": []}):
        out.append(chunk)
    assert "".join(out) == "你好"
