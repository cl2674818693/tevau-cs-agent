# Task 9: 客服侧接管 / 释放 / 收发消息 API

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/api/staff_conversations.py`
- Create: `tests/test_staff_takeover.py`

- [ ] **Step 1: 写 `tests/test_staff_takeover.py`**

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def staff_token(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff
    from ai_engine.auth.staff_session import issue_staff_token
    await init_db()
    await create_staff("S100", "张三", "agent", "x")
    return issue_staff_token("S100", "agent")


async def test_take_and_release(temp_db_url, staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "human_pending")

    transport = ASGITransport(app=main_mod.app)
    headers = {"Authorization": f"Bearer {staff_token}"}
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # 接管
        r = await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=headers)
        assert r.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "human_takeover" and sid == "S100"

        # 再次接管 -> 409
        r2 = await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=headers)
        assert r2.status_code == 409

        # 释放
        r3 = await client.post(f"/staff/api/v1/conversations/{cid}/release", headers=headers)
        assert r3.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "ai" and sid is None


async def test_send_message(temp_db_url, staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, set_mode, list_messages

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "human_takeover", "S100")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "您好，您的卡片已为您解锁。"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert r.status_code == 200

    msgs = await list_messages(cid)
    assert any(m["role"] == "human_agent" and "解锁" in m["content"] for m in msgs)
```

- [ ] **Step 2: 写 `src/ai_engine/api/staff_conversations.py`**

```python
import asyncio
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import get_conn


router = APIRouter()


# 内存订阅总线（生产换 Redis pub/sub）
_subscribers: dict[int, list[asyncio.Queue]] = defaultdict(list)


def _publish(conv_id: int, event: dict) -> None:
    for q in _subscribers.get(conv_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


@router.get("/staff/api/v1/conversations")
async def list_conversations(status: str = Query("human_pending"), staff=Depends(require_staff)):
    return await conv_dao.list_for_staff(status)


@router.post("/staff/api/v1/conversations/{conv_id}/take")
async def take(conv_id: int, staff=Depends(require_staff)):
    # 原子接管：仅 assigned_staff_id IS NULL 时才更新
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE conversations SET mode='human_takeover', assigned_staff_id=?, "
            "assigned_at=datetime('now') "
            "WHERE id=? AND assigned_staff_id IS NULL",
            (staff["sub"], conv_id),
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(409, "already taken by another staff")
    _publish(conv_id, {"type": "mode_changed", "mode": "human_takeover", "staff_id": staff["sub"]})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/release")
async def release(conv_id: int, staff=Depends(require_staff)):
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE conversations SET mode='ai', assigned_staff_id=NULL, assigned_at=NULL "
            "WHERE id=? AND assigned_staff_id=?",
            (conv_id, staff["sub"]),
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(409, "not assigned to you")
    _publish(conv_id, {"type": "mode_changed", "mode": "ai"})
    return {"ok": True}


class StaffMsgIn(BaseModel):
    content: str


@router.post("/staff/api/v1/conversations/{conv_id}/messages")
async def send_message(conv_id: int, body: StaffMsgIn, staff=Depends(require_staff)):
    mode, sid = await conv_dao.get_mode(conv_id)
    if mode != "human_takeover" or sid != staff["sub"]:
        raise HTTPException(403, "not your conversation")
    await conv_dao.append_human_message(conv_id, staff["sub"], body.content)
    _publish(conv_id, {"type": "human_message", "content": body.content, "staff_id": staff["sub"]})
    return {"ok": True}


@router.get("/staff/api/v1/conversations/{conv_id}/stream")
async def stream(conv_id: int, staff=Depends(require_staff)):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[conv_id].append(q)

    async def gen():
        try:
            while True:
                ev = await q.get()
                yield {"event": ev["type"], "data": __import__("json").dumps(ev, ensure_ascii=False)}
        finally:
            _subscribers[conv_id].remove(q)

    return EventSourceResponse(gen())
```

- [ ] **Step 3: 跑测试 + Commit**

```bash
pytest tests/test_staff_takeover.py -v
git add src/ai_engine/api/staff_conversations.py tests/test_staff_takeover.py
git commit -m "feat(mvp-2): 客服 take/release/messages/stream API + 原子接管 409"
```

---
