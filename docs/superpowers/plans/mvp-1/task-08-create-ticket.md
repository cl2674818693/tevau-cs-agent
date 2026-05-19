# Task 8: create_ticket 工具 + mock event center + Lark 兜底

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `src/ai_engine/integrations/lark_webhook.py`
- Create: `src/ai_engine/integrations/event_center_mock.py`
- Create: `src/ai_engine/agent/tools/create_ticket.py`
- Create: `tests/test_create_ticket.py`

- [ ] **Step 1: 写 `tests/test_create_ticket.py`**

```python
import pytest
from unittest.mock import AsyncMock


async def test_create_ticket_posts_to_event_center(seeded_db, monkeypatch):
    from ai_engine.agent.tools import create_ticket
    from ai_engine.persistence.tickets import get_ticket

    posted = []

    async def fake_post(url, json, headers):
        posted.append({"url": url, "json": json, "headers": headers})
        class R: status_code = 200
        return R()

    monkeypatch.setattr(create_ticket, "_post", fake_post)
    monkeypatch.setattr(create_ticket, "_notify_lark", AsyncMock())

    out = await create_ticket.run(
        bu_id="BU00243780",
        conversation_id=1,
        category="bug",
        summary="card_bind 偶发 500",
        severity="p1",
        evidence={"code_refs": [{"repo": "openapi_backend", "path": "handlers/card_bind.py"}]},
    )

    assert out["external_ticket_id"].startswith("AI-")
    # 推送内容
    assert posted and posted[0]["json"]["category"] == "bug"
    assert posted[0]["headers"].get("X-Signature")
    # 本地持久化
    t = await get_ticket(out["external_ticket_id"])
    assert t["payload_json"]


async def test_create_ticket_falls_back_to_lark_when_center_down(seeded_db, monkeypatch):
    from ai_engine.agent.tools import create_ticket

    async def fake_post_failed(url, json, headers):
        raise RuntimeError("network down")

    lark_calls = []

    async def fake_lark(payload):
        lark_calls.append(payload)

    monkeypatch.setattr(create_ticket, "_post", fake_post_failed)
    monkeypatch.setattr(create_ticket, "_notify_lark", fake_lark)

    out = await create_ticket.run(
        bu_id="BU00243780",
        conversation_id=1,
        category="bug",
        summary="x",
        severity="p2",
        evidence={},
    )
    # 工单仍创建成功（本地落库），并触发了 lark 兜底
    assert out["external_ticket_id"]
    assert lark_calls
```

- [ ] **Step 2: 写 `src/ai_engine/integrations/lark_webhook.py`**

```python
import httpx
from ai_engine.config import settings


async def send(payload: dict) -> None:
    if not settings.lark_webhook_url:
        return
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(settings.lark_webhook_url, json={
            "msg_type": "text",
            "content": {"text": payload.get("text", "工单兜底通知")},
        })
```

- [ ] **Step 3: 写 `src/ai_engine/integrations/event_center_mock.py`**

最简 in-process mock：在 FastAPI 里挂载一个 `/_mock/event-center` 路由，记录收到的请求体。供本地联调。

```python
from fastapi import APIRouter, Request


router = APIRouter()
INBOX: list[dict] = []


@router.post("/_mock/event-center")
async def receive(request: Request):
    body = await request.json()
    INBOX.append(body)
    return {"ok": True, "internal_ticket_id": f"EC-MOCK-{len(INBOX):05d}", "received_at": "now"}
```

- [ ] **Step 4: 写 `src/ai_engine/agent/tools/create_ticket.py`**

```python
import hmac
import hashlib
import json
import secrets
from datetime import datetime, timezone
import httpx
from ai_engine.config import settings
from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.tickets import create_ticket as _save_local
from ai_engine.integrations.lark_webhook import send as _notify_lark


VALID_CATEGORIES = {"bug", "事务", "CQ", "无信息", "人工介入"}
VALID_SEVERITIES = {"p0", "p1", "p2", "p3"}


def _new_external_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"AI-{ts}-{secrets.token_hex(3)}"


def _sign(body: bytes) -> str:
    return hmac.new(settings.event_center_secret.encode(), body, hashlib.sha256).hexdigest()


async def _post(url: str, json: dict, headers: dict):
    async with httpx.AsyncClient(timeout=5.0) as client:
        return await client.post(url, json=json, headers=headers)


async def run(
    bu_id: str,
    conversation_id: int,
    category: str,
    summary: str,
    severity: str,
    evidence: dict,
) -> dict:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")

    ext_id = _new_external_id()
    payload = {
        "source": "ai_engine",
        "external_ticket_id": ext_id,
        "user_type": "b",
        "bu_id": bu_id,
        "category": category,
        "summary": summary,
        "severity": severity,
        "evidence": evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. 本地落库（兜底，确保引擎自有记录）
    await _save_local(external_id=ext_id, conversation_id=conversation_id, payload=payload)

    # 2. 推事项中心（带 HMAC 签名）
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-Signature": _sign(body_bytes), "Content-Type": "application/json"}
    pushed = False
    try:
        resp = await _post(settings.event_center_url, json=payload, headers=headers)
        pushed = 200 <= getattr(resp, "status_code", 500) < 300
    except Exception:
        pushed = False

    # 3. 如失败，触发 Lark 兜底
    if not pushed:
        await _notify_lark({"text": f"[兜底] 工单 {ext_id} 推事项中心失败：{category} / {severity} / {summary[:80]}"})

    return {"external_ticket_id": ext_id, "pushed_to_event_center": pushed}


register(Tool(
    name="create_ticket",
    description="当 AI 无法当场解决时，创建工单并推送到事项中心。category ∈ {bug,事务,CQ,无信息,人工介入}，severity ∈ {p0..p3}。**不指定分派人**（分派由事项中心按规则决定，见 spec §7.3）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},
            "category": {"type": "string", "enum": sorted(VALID_CATEGORIES)},
            "summary": {"type": "string", "minLength": 5, "maxLength": 500},
            "severity": {"type": "string", "enum": sorted(VALID_SEVERITIES)},
            "evidence": {"type": "object"},
        },
        "required": ["category", "summary", "severity", "evidence"],
    },
    handler=run,
    requires_subject_id=True,
))
```

注意：`run` 多了一个非 schema 参数 `conversation_id`。Task 5 的 router 已通过 `NEEDS_CONVERSATION_ID` 集合在调 `create_ticket` 时强制注入 `conversation_id`，无需 AI 传，也覆盖 AI 误传。本工具的 `input_schema` 里**不暴露** `conversation_id` —— 让 AI 看不到，避免它瞎填。

- [ ] **Step 5: 跑测试**

```bash
pytest tests/test_create_ticket.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/ai_engine/integrations/lark_webhook.py src/ai_engine/integrations/event_center_mock.py src/ai_engine/agent/tools/create_ticket.py src/ai_engine/agent/tool_router.py tests/test_create_ticket.py
git commit -m "feat: create_ticket 工具 + HMAC 推送 + Lark 兜底 + mock event center receiver"
```

---
