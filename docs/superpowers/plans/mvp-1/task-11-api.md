# Task 11: HTTP API — /api/v1/chat（SSE 流式）+ /api/v1/tickets/{id}/events + main 入口

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `src/ai_engine/auth/__init__.py`
- Create: `src/ai_engine/auth/bu_session.py`
- Create: `src/ai_engine/api/__init__.py`
- Create: `src/ai_engine/api/health.py`
- Create: `src/ai_engine/api/chat.py`
- Create: `src/ai_engine/api/tickets.py`
- Create: `src/ai_engine/main.py`
- Create: `tests/test_chat_api.py`
- Create: `tests/test_tickets_callback.py`

- [ ] **Step 1: 写 `src/ai_engine/auth/bu_session.py`**

MVP-1 简化：从 `X-BU-ID` header 读取 bu_id，便于本地联调。MVP-2 时换 JWT。

```python
from fastapi import HTTPException, Header


async def require_bu(x_bu_id: str = Header(default="")) -> str:
    if not x_bu_id or not x_bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid X-BU-ID")
    return x_bu_id
```

- [ ] **Step 2: 写 `src/ai_engine/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def health():
    return {"ok": True}
```

- [ ] **Step 3: 写 `tests/test_chat_api.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


async def test_chat_endpoint_streams_events(seeded_db, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    async def fake_run_turn(**kwargs):
        yield {"type": "text", "text": "你好"}
        yield {"type": "text", "text": "！"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("POST", "/api/v1/chat",
                                  json={"conversation_id": None, "message": "hi"},
                                  headers={"X-BU-ID": "BU00243780"}) as resp:
            assert resp.status_code == 200
            chunks = []
            async for line in resp.aiter_lines():
                chunks.append(line)
    text_lines = [l for l in chunks if l.startswith("data:")]
    assert any("你好" in l for l in text_lines)


async def test_chat_endpoint_rejects_no_bu_header(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/chat", json={"message": "hi"})
        assert resp.status_code == 401
```

- [ ] **Step 4: 写 `src/ai_engine/api/chat.py`**

```python
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from ai_engine.auth.bu_session import require_bu
from ai_engine.agent import runtime
from ai_engine.persistence.conversations import create_conversation


router = APIRouter()


class ChatIn(BaseModel):
    conversation_id: int | None = None
    message: str


@router.post("/api/v1/chat")
async def chat(body: ChatIn, bu_id: str = Depends(require_bu)):
    conv_id = body.conversation_id
    if conv_id is None:
        conv_id = await create_conversation(user_type="b", subject_id=bu_id)

    async def gen():
        # 注意：SSE 的 data 里也带 type 字段，让前端能用同一个判别联合类型解析
        yield {"event": "conversation",
               "data": json.dumps({"type": "conversation", "conversation_id": conv_id})}
        async for ev in runtime.run_turn(
            conversation_id=conv_id, user_type="b", subject_id=bu_id,
            user_message=body.message,
        ):
            yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({"type": "done"})}

    return EventSourceResponse(gen())
```

- [ ] **Step 5: 写 `tests/test_tickets_callback.py`**

```python
import hmac
import hashlib
import json
import pytest
from httpx import AsyncClient, ASGITransport


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def test_callback_records_event_in_db(seeded_db):
    from ai_engine import main as main_mod
    from ai_engine.persistence.tickets import create_ticket, get_ticket
    from ai_engine.config import settings

    ext_id = "AI-2026-05-18-cb"
    await create_ticket(external_id=ext_id, conversation_id=1, payload={"category": "bug"})

    body = {"event": "assigned", "actor": "嘉豪", "comment": "ok",
            "internal_ticket_id": "EC-1", "at": "now"}
    raw = json.dumps(body).encode("utf-8")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/tickets/{ext_id}/events",
            content=raw,
            headers={"X-Signature": _sign(raw, settings.event_center_secret),
                     "Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    t = await get_ticket(ext_id)
    assert any(e["event"] == "assigned" for e in t["events"])


async def test_callback_rejects_bad_signature(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tickets/xxx/events",
            content=b'{"event":"x"}',
            headers={"X-Signature": "bad", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401
```

- [ ] **Step 6: 写 `src/ai_engine/api/tickets.py`**

```python
import hmac
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, Request
from ai_engine.config import settings
from ai_engine.persistence.tickets import append_ticket_event


router = APIRouter()


def _verify(raw: bytes, sig: str) -> bool:
    expected = hmac.new(settings.event_center_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@router.post("/api/v1/tickets/{external_id}/events")
async def receive_event(external_id: str, request: Request, x_signature: str = Header(default="")):
    raw = await request.body()
    if not _verify(raw, x_signature):
        raise HTTPException(401, "bad signature")
    body = json.loads(raw)
    await append_ticket_event(
        external_id=external_id,
        event=body.get("event", ""),
        actor=body.get("actor"),
        comment=body.get("comment"),
        raw=body,
    )
    return {"ok": True}
```

- [ ] **Step 7: 写 `src/ai_engine/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine.persistence.db import init_db
from ai_engine.api.health import router as health_router
from ai_engine.api.chat import router as chat_router
from ai_engine.api.tickets import router as tickets_router
from ai_engine.integrations.event_center_mock import router as mock_ec_router


app = FastAPI(title="Tevau 客服工单 AI 引擎 (MVP-1)")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(tickets_router)
app.include_router(mock_ec_router)


@app.on_event("startup")
async def _startup():
    await init_db()
```

- [ ] **Step 8: 跑测试**

```bash
pytest tests/test_chat_api.py tests/test_tickets_callback.py -v
```
Expected: 4 passed

- [ ] **Step 9: Commit**

```bash
git add src/ai_engine/auth src/ai_engine/api src/ai_engine/main.py tests/test_chat_api.py tests/test_tickets_callback.py
git commit -m "feat: HTTP API（/chat SSE 流 + /tickets/:id/events 回调）+ FastAPI 入口"
```

---
