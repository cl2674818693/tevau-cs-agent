# Task 10: Agent runtime（loop + tool 调度 + 流式输出）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `server/src/ai_engine/agent/runtime.py`
- Create: `server/tests/test_agent_runtime.py`

agent loop 的核心：拿到用户消息 → 用 system blocks + history + tools 调 Anthropic → 流出文本 + 解析 tool_use → dispatch → 把 tool_result 接回 messages → 再调 → 直到没有 tool_use 或触发 cost guard。

- [ ] **Step 1: 写 `server/tests/test_agent_runtime.py`（用 mock client 端到端走一遍）**

```python
import pytest
from unittest.mock import MagicMock, AsyncMock


async def test_runtime_runs_tool_then_replies(seeded_db, monkeypatch):
    """模拟：第一次模型返回 tool_use(search_code)；第二次返回纯文本。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    call_seq = []

    class FakeResp:
        def __init__(self, blocks, stop_reason):
            self.content = blocks
            self.stop_reason = stop_reason
            self.usage = MagicMock(input_tokens=10, output_tokens=10)

    async def fake_create(**kwargs):
        call_seq.append(kwargs)
        if len(call_seq) == 1:
            return FakeResp([
                MagicMock(type="tool_use", id="t1", name="search_code",
                          input={"repo": "openapi_backend", "query": "card_bind"}),
            ], "tool_use")
        return FakeResp([MagicMock(type="text", text="结论：handler 在 card_bind.py。证据：search_code 命中。")],
                        "end_turn")

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr(ac, "_client", fake_client)
    # 让 search_code 工具调用走通：注入 repos_root
    import os
    from pathlib import Path
    monkeypatch.setenv("CODE_REPOS_ROOT", str(Path("tests/fixtures").resolve()))
    Path("tests/fixtures/openapi_backend").symlink_to(
        Path("tests/fixtures/sample_repo").resolve(), target_is_directory=True
    ) if not Path("tests/fixtures/openapi_backend").exists() else None
    from ai_engine.config import settings
    settings.reload()

    chunks = []
    async for ev in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="BU00243780",
        user_message="card_bind 接口 500 怎么回事？",
    ):
        chunks.append(ev)
    # 至少一次 tool_call、一次 text
    kinds = [c["type"] for c in chunks]
    assert "tool_call" in kinds
    assert "text" in kinds
    assert "结论" in "".join(c.get("text", "") for c in chunks if c["type"] == "text")
```

- [ ] **Step 2: 跑确认失败**

```bash
pytest tests/test_agent_runtime.py -v
```
Expected: FAIL

- [ ] **Step 3: 写 `server/src/ai_engine/agent/runtime.py`**

```python
import json
from typing import AsyncIterator
from ai_engine.config import settings
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.integrations.anthropic_client import build_messages_request
from ai_engine.prompts.loader import build_system_blocks
from ai_engine.agent.tool_router import dispatch
from ai_engine.agent.cost_guard import CostGuard
from ai_engine.agent.tools import base  # 触发工具注册
from ai_engine.agent.tools import (  # noqa: F401
    search_code, read_file, query_user, query_card, query_api_call, lookup_api_doc, create_ticket,
)
from ai_engine.persistence.conversations import append_message


def _block_to_dict(b) -> dict:
    """把 anthropic 返回的 block (object 或 dict) 都规整为 dict。"""
    if isinstance(b, dict):
        return b
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": getattr(b, "text", "")}
    if t == "tool_use":
        return {"type": "tool_use", "id": getattr(b, "id"),
                "name": getattr(b, "name"), "input": getattr(b, "input", {})}
    return {"type": t or "unknown"}


async def run_turn(
    *,
    conversation_id: int,
    user_type: str,
    subject_id: str,
    user_message: str,
    model: str | None = None,
) -> AsyncIterator[dict]:
    model = model or settings.default_model
    system_blocks = build_system_blocks(user_type=user_type)
    tools = base.all_definitions()

    messages: list[dict] = [{"role": "user", "content": user_message}]
    await append_message(conversation_id, role="user", content=user_message)

    guard = CostGuard(max_depth=settings.max_tool_depth,
                      max_result_bytes=settings.max_tool_result_bytes)

    while True:
        req = build_messages_request(
            system_blocks=system_blocks, messages=messages, tools=tools, model=model,
        )
        # 通过模块属性引用，便于测试用 monkeypatch.setattr 替换
        resp = await _ac._client.messages.create(**req)
        blocks = [_block_to_dict(b) for b in resp.content]

        # 累积本轮 assistant 内容
        assistant_blocks: list[dict] = []
        tool_calls_in_round: list[dict] = []
        for b in blocks:
            if b["type"] == "text":
                assistant_blocks.append(b)
                yield {"type": "text", "text": b["text"]}
            elif b["type"] == "tool_use":
                assistant_blocks.append(b)
                tool_calls_in_round.append(b)
                yield {"type": "tool_call", "name": b["name"], "input": b["input"]}

        if assistant_blocks:
            messages.append({"role": "assistant", "content": assistant_blocks})
            await append_message(
                conversation_id, role="assistant",
                content=json.dumps([
                    b for b in assistant_blocks if b["type"] == "text"
                ], ensure_ascii=False),
            )

        if resp.stop_reason != "tool_use" or not tool_calls_in_round:
            return  # 结束

        # 调用本轮所有 tool_use
        tool_results_block = []
        for tc in tool_calls_in_round:
            if not guard.can_call_again():
                tool_results_block.append({
                    "type": "tool_result", "tool_use_id": tc["id"],
                    "content": "ERROR: 达到工具调用深度上限，请直接给出当前结论或建工单。",
                    "is_error": True,
                })
                continue
            guard.note_call()
            r = await dispatch(
                tool_name=tc["name"], params=tc["input"],
                user_type=user_type, subject_id=subject_id,
                conversation_id=conversation_id,
            )
            payload = json.dumps(r.get("data") if r["ok"] else {"error": r["error"]}, ensure_ascii=False)
            payload, truncated = guard.maybe_truncate(payload)
            if truncated:
                payload += "\n[TRUNCATED]"
            tool_results_block.append({
                "type": "tool_result", "tool_use_id": tc["id"], "content": payload,
                "is_error": not r["ok"],
            })
            yield {"type": "tool_result", "name": tc["name"], "ok": r["ok"]}

        messages.append({"role": "user", "content": tool_results_block})
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_agent_runtime.py -v
```
Expected: passed（可能需要调 mock 细节）

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/agent/runtime.py server/tests/test_agent_runtime.py
git commit -m "feat: agent runtime (loop + tool 调度 + cost guard)"
```

---
