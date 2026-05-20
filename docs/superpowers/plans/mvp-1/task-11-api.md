# Task 11: HTTP API — /chat（SSE 流） + /conversations 初始化 + /tickets/{id}/events 回调 + main 入口

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

对齐 spec §3.3（SSE 协议契约：事件类型 / 心跳 30s / Last-Event-ID 重连 / 错误码 / 80% 阈值 warning）/ §6.2（会话初始化端点 POST /api/v1/conversations）/ §7.2 修订（webhook 入口 schema 加 severity 可选字段）/ §3.3 取消生成端点 DELETE /api/v1/chat/{id}/stream。

**Files:**
- Create: `server/src/ai_engine/auth/__init__.py`
- Create: `server/src/ai_engine/auth/bu_session.py`
- Create: `server/src/ai_engine/api/__init__.py`
- Create: `server/src/ai_engine/api/health.py`
- Create: `server/src/ai_engine/api/conversations.py`（会话初始化）
- Create: `server/src/ai_engine/api/chat.py`（SSE 流 + 取消生成）
- Create: `server/src/ai_engine/api/tickets.py`（事项中心回调，含 severity 解析）
- Create: `server/src/ai_engine/api/sse_events.py`（事件类型常量 + helper）
- Create: `server/src/ai_engine/main.py`
- Create: `server/tests/test_chat_api.py`
- Create: `server/tests/test_conversations_api.py`
- Create: `server/tests/test_tickets_callback.py`

- [ ] **Step 1: 写 `server/src/ai_engine/auth/bu_session.py`**

MVP-1 简化：从 `X-BU-ID` header 读取 bu_id，便于本地联调。MVP-2 时换 JWT。

```python
from fastapi import HTTPException, Header


async def require_bu(x_bu_id: str = Header(default="")) -> str:
    if not x_bu_id or not x_bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid X-BU-ID")
    return x_bu_id
```

- [ ] **Step 2: 写 `server/src/ai_engine/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def health():
    return {"ok": True}
```

- [ ] **Step 3: 写 `server/src/ai_engine/api/sse_events.py`**（事件类型常量 + helper，对齐 spec §3.3）

```python
"""SSE 事件类型常量与 helper。对齐 spec §3.3 SSE 协议契约。

所有 SSE event 名都从这里取，避免 chat.py / runtime / 前端拼写不一致。
"""
from typing import Literal

# 完整事件类型清单（spec §3.3 表）
EVENT_CONVERSATION = "conversation"            # 首事件：携带 user_type / conversation_id / model
EVENT_MESSAGE_START = "message_start"          # assistant 消息开始
EVENT_CONTENT_BLOCK_DELTA = "content_block_delta"   # 文本流式增量
EVENT_TOOL_USE = "tool_use"                    # AI 决定调工具
EVENT_TOOL_RESULT = "tool_result"              # 工具返回（已脱敏）
EVENT_MESSAGE_STOP = "message_stop"            # assistant 消息结束（含 stop_reason）
EVENT_TICKET_EVENT = "ticket_event"            # 工单状态推送（MVP-3 替换轮询）
EVENT_MODE_CHANGE = "mode_change"              # mode 切换（MVP-2 上线）
EVENT_HUMAN_MESSAGE = "human_message"          # 客服消息（MVP-2 上线）
EVENT_ERROR = "error"                          # 错误（见错误码表）
EVENT_WARNING = "warning"                      # 警告（如 80% token 阈值）
EVENT_PING = "ping"                            # 心跳

# 错误码（spec §3.3 错误码表）
ErrorCode = Literal[
    "AUTH_EXPIRED",
    "RATE_LIMITED",
    "TOOL_DEPTH_EXCEEDED",
    "MODEL_OVERLOADED",
    "CONVERSATION_NOT_FOUND",
    "INTERNAL_ERROR",
]

PING_INTERVAL_SECONDS = 30
CLIENT_IDLE_TIMEOUT_SECONDS = 60   # 客户端 60s 无事件视为断线，主动重连


def sse_payload(event: str, data: dict, event_id: str | None = None) -> dict:
    """构造 sse-starlette EventSourceResponse 期望的 dict 格式。"""
    import json
    out: dict = {"event": event, "data": json.dumps(data, ensure_ascii=False)}
    if event_id is not None:
        out["id"] = event_id        # 客户端用 Last-Event-ID 头携带，服务端从该 id 后补推
    return out


def error_event(code: ErrorCode, message: str, retry_after_ms: int | None = None) -> dict:
    payload = {"code": code, "message": message}
    if retry_after_ms is not None:
        payload["retry_after_ms"] = retry_after_ms
    return sse_payload(EVENT_ERROR, payload)
```

- [ ] **Step 4: 写 `server/tests/test_conversations_api.py`**（会话初始化端点测试，spec §6.2）

```python
import pytest
from httpx import AsyncClient, ASGITransport


async def test_conversations_init_returns_user_type_b(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/conversations", json={},
            headers={"X-BU-ID": "BU00243780"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_type"] == "b"
    assert body["conversation_id"]
    assert body["display_name"]
    assert body["greeting"]
    assert "limits" in body


async def test_conversations_init_rejects_no_bu(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/conversations", json={})
    assert resp.status_code == 401
```

- [ ] **Step 5: 写 `server/src/ai_engine/api/conversations.py`**（spec §6.2）

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ai_engine.auth.bu_session import require_bu
from ai_engine.persistence.conversations import create_conversation


router = APIRouter()


class ConversationsInitIn(BaseModel):
    resume: int | None = None     # 可选：传入则恢复历史会话；MVP-1 暂不实现


class ConversationsInitOut(BaseModel):
    conversation_id: int
    user_type: str
    display_name: str
    greeting: str
    history_url: str | None = None
    limits: dict


@router.post("/api/v1/conversations")
async def init_conversation(
    body: ConversationsInitIn,
    bu_id: str = Depends(require_bu),
) -> ConversationsInitOut:
    # MVP-1：B 端固定 greeting；display_name 用 BU_ID（脱敏后续接 query_bu 时再补）
    conv_id = await create_conversation(user_type="b", subject_id=bu_id)
    return ConversationsInitOut(
        conversation_id=conv_id,
        user_type="b",
        display_name=bu_id,                # MVP-1 简化
        greeting="您好，我是 Tevau 智能助手，可以帮您查 Open API / 卡片业务相关问题。",
        history_url=None,                  # MVP-1 不支持历史恢复
        limits={"daily_token_used_pct": 0, "max_turns": 20},
    )
```

- [ ] **Step 6: 写 `server/tests/test_chat_api.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


async def test_chat_endpoint_streams_events(seeded_db, monkeypatch):
    """SSE 主链路：首事件 conversation → message_start/content_block_delta... → message_stop"""
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    # runtime 流出领域事件（text/tool_call），chat.py 映射成 spec §3.3 wire 事件
    async def fake_run_turn(**kwargs):
        yield {"type": "text", "text": "你好"}
        yield {"type": "text", "text": "！"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 先初始化会话
        init = await client.post("/api/v1/conversations", json={},
                                 headers={"X-BU-ID": "BU00243780"})
        conv_id = init.json()["conversation_id"]
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={conv_id}",
            params={"message": "hi"}, headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            assert resp.status_code == 200
            chunks = []
            async for line in resp.aiter_lines():
                chunks.append(line)
    # 必须包含 conversation 首事件 + content_block_delta 文本 + message_stop
    assert any("event: conversation" in l for l in chunks)
    assert any("content_block_delta" in l for l in chunks)
    assert any("你好" in l for l in chunks)
    assert any("message_stop" in l for l in chunks)


async def test_chat_endpoint_emits_ping(seeded_db, monkeypatch):
    """spec §3.3: 心跳每 30s 一次。测试用快速 ping interval 验证 helper 路径。"""
    from ai_engine.api import sse_events
    assert sse_events.PING_INTERVAL_SECONDS == 30


async def test_chat_endpoint_rejects_no_bu_header(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/chat?conversation_id=1")
        assert resp.status_code == 401


async def test_chat_cancel_stream(seeded_db, monkeypatch):
    """spec §3.3: DELETE /api/v1/chat/{conv_id}/stream → 中断 Anthropic 调用 + 推 message_stop(cancelled)"""
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init = await client.post("/api/v1/conversations", json={},
                                 headers={"X-BU-ID": "BU00243780"})
        conv_id = init.json()["conversation_id"]
        resp = await client.delete(f"/api/v1/chat/{conv_id}/stream",
                                    headers={"X-BU-ID": "BU00243780"})
    assert resp.status_code == 204
```

- [ ] **Step 7: 写 `server/src/ai_engine/api/chat.py`**（含 SSE 完整契约 + 心跳 + 取消生成）

runtime 流出领域事件（text/tool_call/tool_result），chat.py 用 `_map_runtime_event` 映射成 spec §3.3 wire 事件（content_block_delta / tool_use / tool_result），并在前后包 conversation / message_start / message_stop。心跳用 sse-starlette 内置 `ping=` 参数，不手写并发（更可靠）。

```python
import asyncio
import secrets
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Query
from sse_starlette.sse import EventSourceResponse

from ai_engine.agent import runtime
from ai_engine.api import sse_events as se
from ai_engine.auth.bu_session import require_bu

router = APIRouter()

# conversation_id → asyncio.Event（用户点"停止生成"时 set，gen() 检测后退出）
_cancel_signals: dict[int, asyncio.Event] = {}


def _map_runtime_event(ev: dict[str, Any]) -> dict[str, str] | None:
    """runtime 领域事件 → spec §3.3 wire 事件。"""
    t = ev.get("type")
    if t == "text":
        return se.sse_payload(se.EVENT_CONTENT_BLOCK_DELTA,
                              {"index": 0, "delta": {"type": "text_delta", "text": ev.get("text", "")}})
    if t == "tool_call":
        return se.sse_payload(se.EVENT_TOOL_USE, {"name": ev.get("name"), "input": ev.get("input")})
    if t == "tool_result":
        return se.sse_payload(se.EVENT_TOOL_RESULT,
                              {"name": ev.get("name"), "is_error": not ev.get("ok", False)})
    return None


@router.get("/api/v1/chat")
async def chat(
    conversation_id: int = Query(...),
    message: str = Query(...),
    bu_id: str = Depends(require_bu),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """SSE 主链路。Last-Event-ID 用于重连补推（MVP-1 简化：仅记录、不实际补推）。"""
    cancel_evt = asyncio.Event()
    _cancel_signals[conversation_id] = cancel_evt

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            yield se.sse_payload(se.EVENT_CONVERSATION, {
                "conversation_id": conversation_id, "user_type": "b", "model": "claude-sonnet-4-6",
            })
            yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
            async for ev in runtime.run_turn(
                conversation_id=conversation_id, user_type="b",
                subject_id=bu_id, user_message=message,
            ):
                if cancel_evt.is_set():
                    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "cancelled"})
                    return
                mapped = _map_runtime_event(ev)
                if mapped is not None:
                    yield mapped
            yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "end_turn"})
        except Exception as e:  # 顶层兜底，错误转 SSE error 事件
            yield se.error_event("INTERNAL_ERROR", str(e))
        finally:
            _cancel_signals.pop(conversation_id, None)

    return EventSourceResponse(gen(), ping=se.PING_INTERVAL_SECONDS)


@router.delete("/api/v1/chat/{conversation_id}/stream", status_code=204)
async def cancel_stream(conversation_id: int, bu_id: str = Depends(require_bu)):
    """用户点"停止生成"。中断 Anthropic 调用，gen() 检测信号后 yield message_stop(cancelled) 并关闭流。"""
    evt = _cancel_signals.get(conversation_id)
    if evt:
        evt.set()
```

- [ ] **Step 8: 写 `server/tests/test_tickets_callback.py`**

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


async def test_callback_parses_severity_override(seeded_db):
    """spec §7.2 修订：event=in_progress 时可携带 severity（受理人在事项中心覆盖）"""
    from ai_engine import main as main_mod
    from ai_engine.persistence.tickets import create_ticket, get_ticket
    from ai_engine.config import settings

    ext_id = "AI-2026-05-18-sev"
    await create_ticket(external_id=ext_id, conversation_id=1,
                         payload={"category": "bug", "severity": "p2"})

    body = {"event": "in_progress", "actor": "嘉豪",
            "internal_ticket_id": "EC-2", "severity": "p0",   # 受理人覆盖 p2 → p0
            "at": "now"}
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
    assert t["current_severity"] == "p0"        # 本地镜像更新


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

- [ ] **Step 9: 写 `server/src/ai_engine/api/tickets.py`**

```python
import hmac
import hashlib
import json
from fastapi import APIRouter, Header, HTTPException, Request
from ai_engine.config import settings
from ai_engine.persistence.tickets import append_ticket_event, update_ticket_severity


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
    # spec §7.2 修订：event=in_progress 时可带 severity（受理人在事项中心覆盖）
    if body.get("event") == "in_progress" and body.get("severity"):
        await update_ticket_severity(external_id=external_id, severity=body["severity"])
    return {"ok": True}
```

- [ ] **Step 10: 写 `server/src/ai_engine/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ai_engine.persistence.db import init_db
from ai_engine.api.health import router as health_router
from ai_engine.api.conversations import router as conversations_router
from ai_engine.api.chat import router as chat_router
from ai_engine.api.tickets import router as tickets_router
from ai_engine.integrations.event_center_mock import router as mock_ec_router


app = FastAPI(title="Tevau 客服工单 AI 引擎 (MVP-1)")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    expose_headers=["Last-Event-ID"],     # SSE 重连支持，spec §3.3
)
app.include_router(health_router)
app.include_router(conversations_router)
app.include_router(chat_router)
app.include_router(tickets_router)
app.include_router(mock_ec_router)


@app.on_event("startup")
async def _startup():
    await init_db()
```

- [ ] **Step 11: 跑测试**

```bash
(cd server && pytest tests/test_chat_api.py tests/test_tickets_callback.py tests/test_conversations_api.py -v)
```
Expected: 8 passed（4 chat + 2 conversations + 2 tickets-callback；其中 tickets-callback 含 severity override 测试）

- [ ] **Step 12: Commit**

```bash
git add server/src/ai_engine/auth server/src/ai_engine/api server/src/ai_engine/main.py \
    server/tests/test_chat_api.py server/tests/test_tickets_callback.py server/tests/test_conversations_api.py
git commit -m "feat: HTTP API（/conversations 初始化 + /chat SSE 完整契约 + DELETE 取消生成 + /tickets/:id/events 含 severity）+ FastAPI 入口"
```

---
