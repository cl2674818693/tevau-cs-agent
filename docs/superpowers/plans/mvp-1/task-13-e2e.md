# Task 13: 端到端 MVP-1 验收

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `server/tests/test_e2e_mvp1.py`

这是 spec §10 的验收标准的可执行表达。用 mock 的 Anthropic client 模拟两个场景：

1. 越权场景：AI 试图查另一个 BU 的卡片 → 服务端拒绝 → AI 回复"无权查询其他 BU"
2. bug 诊断场景：AI 查 api_call 拿到日志 → search_code 定位代码 → 建工单 → mock event center 收到推送

- [ ] **Step 1: 写 `server/tests/test_e2e_mvp1.py`**

```python
import json
import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport


def _block(type_, **kw):
    m = MagicMock()
    m.type = type_
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _resp(blocks, stop_reason):
    r = MagicMock()
    r.content = blocks
    r.stop_reason = stop_reason
    r.usage = MagicMock(input_tokens=10, output_tokens=10)
    return r


async def test_e2e_bug_diagnosis_creates_ticket(seeded_db, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.integrations import event_center_mock as ec_mock

    seq = iter([
        _resp([_block("tool_use", id="1", name="query_api_call",
                      input={"uid": "1765348436409"})], "tool_use"),
        _resp([_block("tool_use", id="2", name="search_code",
                      input={"repo": "openapi_backend", "query": "card_bind"})], "tool_use"),
        _resp([_block("tool_use", id="3", name="create_ticket",
                      input={"category": "bug", "summary": "card_bind 偶发 500 + DB_TIMEOUT",
                             "severity": "p1",
                             "evidence": {"code_refs": [{"repo": "openapi_backend",
                                                          "path": "handlers/card_bind.py"}],
                                          "data_refs": [{"uid": "1765348436409",
                                                          "status_code": 500}]}})], "tool_use"),
        _resp([_block("text", text="已为您创建 bug 工单 AI-...。证据：500 + DB_TIMEOUT。")],
              "end_turn"),
    ])

    async def fake_create(**kwargs):
        return next(seq)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr(ac, "_client", fake_client)
    # 重定向 event center 到本进程 mock
    monkeypatch.setenv("EVENT_CENTER_URL", "http://localhost/_mock/event-center")
    from ai_engine.config import settings
    settings.reload()

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        async with client.stream(
            "POST", "/api/v1/chat",
            json={"conversation_id": None,
                  "message": "BU00243780 的 /v2/card/bind 偶发 500，uid=1765348436409"},
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            assert resp.status_code == 200
            tool_results: list[str] = []
            async for line in resp.aiter_lines():
                if line.startswith("data:") and '"type":"tool_result"' in line:
                    tool_results.append(line)

    # 4 个工具结果（除最后 text 外）
    assert len(tool_results) == 3
    # 工单进了 mock event center
    assert ec_mock.INBOX, "event center mock should have received a ticket"
    assert ec_mock.INBOX[-1]["category"] == "bug"


async def test_e2e_cross_bu_query_is_blocked(seeded_db, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac

    seq = iter([
        _resp([_block("tool_use", id="1", name="query_card",
                      input={"bu_id": "BU_OTHER", "card_id": "1111222233334444"})], "tool_use"),
        _resp([_block("text",
                      text="未在您 BU 下找到该卡片。我没有权限查询其他 BU 的数据。")],
              "end_turn"),
    ])

    async def fake_create(**kwargs):
        return next(seq)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr(ac, "_client", fake_client)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        async with client.stream(
            "POST", "/api/v1/chat",
            json={"message": "查一下卡 1111222233334444"},
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            text_chunks: list[str] = []
            async for line in resp.aiter_lines():
                if line.startswith("data:") and '"type":"text"' in line:
                    text_chunks.append(line)

    joined = "\n".join(text_chunks)
    assert "未在您 BU 下" in joined or "其他 BU" in joined
```

- [ ] **Step 2: 跑端到端测试**

```bash
pytest tests/test_e2e_mvp1.py -v
```
Expected: 2 passed

- [ ] **Step 3: 跑全套测试**

```bash
pytest -v
```
Expected: 全部 passed

- [ ] **Step 4: Commit**

```bash
git add server/tests/test_e2e_mvp1.py
git commit -m "test: MVP-1 端到端验收（bug 诊断建单 + 越权拒绝）"
```

---
