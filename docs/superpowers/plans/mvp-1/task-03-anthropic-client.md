# Task 3: Anthropic 客户端封装（含 prompt cache）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `src/ai_engine/integrations/__init__.py`
- Create: `src/ai_engine/integrations/anthropic_client.py`
- Create: `tests/test_anthropic_client.py`

- [ ] **Step 1: 写 `tests/test_anthropic_client.py`（失败测试，用 mock client）**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


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
    # system 的每一块都应被标记 cache_control = ephemeral
    assert all(b.get("cache_control", {}).get("type") == "ephemeral" for b in req["system"])
    assert req["model"] == "claude-sonnet-4-6"
    assert req["tools"][0]["name"] == "search_code"
    assert req["messages"][0]["content"] == "你好"


async def test_stream_yields_text_deltas(monkeypatch):
    """烟雾测试：stream 函数能 yield 文本增量。用 mock Anthropic 客户端。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.integrations import anthropic_client as ac

    fake_events = [
        MagicMock(type="content_block_delta",
                  delta=MagicMock(type="text_delta", text="你")),
        MagicMock(type="content_block_delta",
                  delta=MagicMock(type="text_delta", text="好")),
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
```

- [ ] **Step 2: 跑确认失败**

```bash
pytest tests/test_anthropic_client.py -v
```
Expected: ImportError / FAIL

- [ ] **Step 3: 写 `src/ai_engine/integrations/__init__.py`（空文件）**

- [ ] **Step 4: 写 `src/ai_engine/integrations/anthropic_client.py`**

```python
from anthropic import AsyncAnthropic
from ai_engine.config import settings


_client = AsyncAnthropic(api_key=settings.anthropic_api_key)


def build_messages_request(
    *,
    system_blocks: list[dict],
    messages: list[dict],
    tools: list[dict] | None,
    model: str,
    max_tokens: int = 4096,
) -> dict:
    """构造 Anthropic Messages API 请求体，对每个 system 块加 ephemeral cache_control。"""
    cached_system = []
    for blk in system_blocks:
        blk = {**blk, "cache_control": {"type": "ephemeral"}}
        cached_system.append(blk)
    return {
        "model": model,
        "system": cached_system,
        "messages": messages,
        "tools": tools or [],
        "max_tokens": max_tokens,
    }


async def stream_text_only(request_body: dict):
    """只 yield 文本增量。给后续 agent runtime 用 stream 的复杂版替换。"""
    async with _client.messages.stream(**request_body) as stream:
        async for ev in stream:
            if getattr(ev, "type", None) == "content_block_delta":
                delta = getattr(ev, "delta", None)
                if delta and getattr(delta, "type", None) == "text_delta":
                    yield delta.text
```

- [ ] **Step 5: 跑测试确认通过**

```bash
pytest tests/test_anthropic_client.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/ai_engine/integrations/__init__.py src/ai_engine/integrations/anthropic_client.py tests/test_anthropic_client.py
git commit -m "feat: Anthropic 客户端封装（含 prompt cache 标注）"
```

---
