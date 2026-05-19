# Task 5: 工具路由 + 身份强制注入 + cost guard

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `src/ai_engine/agent/tool_router.py`
- Create: `src/ai_engine/agent/cost_guard.py`
- Create: `tests/test_tool_router_authz.py`
- Create: `tests/test_cost_guard.py`

- [ ] **Step 1: 写 `tests/test_tool_router_authz.py`**

```python
import pytest


async def test_router_injects_subject_id_for_subject_required_tool(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.agent.tools import base
    from ai_engine.agent.tool_router import dispatch

    async def fake_handler(bu_id: str):
        return {"bu_id": bu_id}

    base.register(base.Tool(
        name="query_bu_fake",
        description="fake",
        input_schema={"type": "object", "properties": {"bu_id": {"type": "string"}}},
        handler=fake_handler,
        requires_subject_id=True,
    ))

    # AI 试图传 bu_id=BU_OTHER，router 应强制覆盖为会话身份 BU00243780
    result = await dispatch(
        tool_name="query_bu_fake",
        params={"bu_id": "BU_OTHER"},
        user_type="b",
        subject_id="BU00243780",
        conversation_id=1,
    )
    assert result["ok"] is True
    assert result["data"]["bu_id"] == "BU00243780"


async def test_router_rejects_unknown_tool(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from ai_engine.agent.tool_router import dispatch
    out = await dispatch(
        tool_name="nope", params={}, user_type="b", subject_id="BU1", conversation_id=1,
    )
    assert out["ok"] is False
    assert "unknown" in out["error"]


async def test_router_audits_call(monkeypatch, temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.audit import list_audits
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base

    async def fake_ok(x: str):
        return {"echo": x}

    base.register(base.Tool(
        name="echo_tool", description="", input_schema={"type": "object"},
        handler=fake_ok, requires_subject_id=False,
    ))

    await init_db()
    await dispatch(tool_name="echo_tool", params={"x": "hi"}, user_type="b",
                   subject_id="BU1", conversation_id=1)
    rows = await list_audits(conversation_id=1)
    assert rows and rows[0]["tool_name"] == "echo_tool"
```

- [ ] **Step 2: 写 `tests/test_cost_guard.py`**

```python
import pytest


def test_cost_guard_limits_depth():
    from ai_engine.agent.cost_guard import CostGuard
    g = CostGuard(max_depth=3, max_result_bytes=1024)
    assert g.can_call_again() is True
    g.note_call(); g.note_call(); g.note_call()
    assert g.can_call_again() is False


def test_cost_guard_truncates_large_result():
    from ai_engine.agent.cost_guard import CostGuard
    g = CostGuard(max_depth=12, max_result_bytes=10)
    out, truncated = g.maybe_truncate("a" * 100)
    assert truncated is True
    assert len(out) <= 10
```

- [ ] **Step 3: 跑确认失败**

```bash
pytest tests/test_tool_router_authz.py tests/test_cost_guard.py -v
```
Expected: FAIL

- [ ] **Step 4: 写 `src/ai_engine/agent/cost_guard.py`**

```python
from dataclasses import dataclass


@dataclass
class CostGuard:
    max_depth: int
    max_result_bytes: int
    _calls: int = 0

    def can_call_again(self) -> bool:
        return self._calls < self.max_depth

    def note_call(self) -> None:
        self._calls += 1

    def maybe_truncate(self, payload: str) -> tuple[str, bool]:
        b = payload.encode("utf-8")
        if len(b) <= self.max_result_bytes:
            return payload, False
        return b[: self.max_result_bytes].decode("utf-8", errors="ignore"), True
```

- [ ] **Step 5: 写 `src/ai_engine/agent/tool_router.py`**

```python
import json
import time
from typing import Any
from ai_engine.agent.tools import base
from ai_engine.persistence.audit import log_tool_call


NEEDS_CONVERSATION_ID = {"create_ticket"}


def _subject_param_name(user_type: str) -> str:
    return "bu_id" if user_type == "b" else "user_id"


async def dispatch(
    *,
    tool_name: str,
    params: dict,
    user_type: str,
    subject_id: str,
    conversation_id: int,
) -> dict[str, Any]:
    tool = base.get(tool_name)
    if tool is None:
        await log_tool_call(conversation_id, tool_name, params, 0, 0, True, "unknown tool")
        return {"ok": False, "error": f"unknown tool: {tool_name}"}

    # 身份注入：把 subject_id 强写入对应字段，覆盖 AI 传值
    safe_params = dict(params)
    if tool.requires_subject_id:
        safe_params[_subject_param_name(user_type)] = subject_id
    # 个别工具需要 conversation_id（如 create_ticket）；统一注入
    if tool_name in NEEDS_CONVERSATION_ID:
        safe_params["conversation_id"] = conversation_id

    started = time.perf_counter()
    try:
        data = await tool.handler(**safe_params)
        duration_ms = int((time.perf_counter() - started) * 1000)
        payload = json.dumps(data, ensure_ascii=False)
        await log_tool_call(conversation_id, tool_name, safe_params,
                            len(payload.encode("utf-8")), duration_ms, False, None)
        return {"ok": True, "data": data}
    except ValueError as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(conversation_id, tool_name, safe_params, 0, duration_ms, True, str(e))
        return {"ok": False, "error": f"invalid args: {e}"}
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(conversation_id, tool_name, safe_params, 0, duration_ms, True, f"internal: {e}")
        return {"ok": False, "error": f"internal error"}
```

- [ ] **Step 6: 跑测试**

```bash
pytest tests/test_tool_router_authz.py tests/test_cost_guard.py -v
```
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add src/ai_engine/agent/tool_router.py src/ai_engine/agent/cost_guard.py tests/test_tool_router_authz.py tests/test_cost_guard.py
git commit -m "feat: 工具路由（身份强制注入 + 审计）与 cost guard"
```

---
