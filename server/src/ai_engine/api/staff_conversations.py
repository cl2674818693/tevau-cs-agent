import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import get_conn

router = APIRouter()

# 内存订阅总线（单进程；生产多副本时换 Redis pub/sub）
_subscribers: dict[int, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


def _publish(conv_id: int, event: dict[str, Any]) -> None:
    for q in _subscribers.get(conv_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def publish_user_message(conv_id: int, content: str) -> None:
    """human_takeover/pending 时，chat 端点把用户消息推到订阅该会话的客服侧。"""
    _publish(conv_id, {"type": "user_message", "content": content})


def publish_ai_draft(conv_id: int, draft: str) -> None:
    """ai_draft 模式：AI 草稿推到客服侧待 review。"""
    _publish(conv_id, {"type": "ai_draft_ready", "draft": draft})


@router.get("/staff/api/v1/conversations")
async def list_conversations(
    status: str = Query("human_pending"),
    staff: dict[str, Any] = Depends(require_staff),
) -> list[dict[str, object]]:
    return await conv_dao.list_for_staff(status)


@router.post("/staff/api/v1/conversations/{conv_id}/take")
async def take(conv_id: int, staff: dict[str, Any] = Depends(require_staff)) -> dict[str, bool]:
    # 原子接管：仅 assigned_staff_id IS NULL 时才更新（防多客服抢同一会话）
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
    _publish(conv_id, {"type": "mode_change", "to": "human_takeover", "by_staff_id": staff["sub"]})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/release")
async def release(conv_id: int, staff: dict[str, Any] = Depends(require_staff)) -> dict[str, bool]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE conversations SET mode='ai', assigned_staff_id=NULL, assigned_at=NULL "
            "WHERE id=? AND assigned_staff_id=?",
            (conv_id, staff["sub"]),
        )
        await conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(409, "not assigned to you")
    _publish(conv_id, {"type": "mode_change", "to": "ai"})
    return {"ok": True}


class StaffMsgIn(BaseModel):
    content: str


@router.post("/staff/api/v1/conversations/{conv_id}/messages")
async def send_message(
    conv_id: int, body: StaffMsgIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    mode, sid = await conv_dao.get_mode(conv_id)
    if mode != "human_takeover" or sid != staff["sub"]:
        raise HTTPException(403, "not your conversation")
    await conv_dao.append_human_message(conv_id, staff["sub"], body.content)
    _publish(
        conv_id,
        {"type": "human_message", "content": body.content, "sender_staff_id": staff["sub"]},
    )
    return {"ok": True}


async def _require_assigned(conv_id: int, staff_sub: str) -> None:
    _, sid = await conv_dao.get_mode(conv_id)
    if sid != staff_sub:
        raise HTTPException(403, "not your conversation")


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
async def ai_draft_enable(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    """切到 ai_draft：AI 出草稿、客服 review 后发。先把会话指派给本客服。"""
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE conversations SET mode='ai_draft', assigned_staff_id=?, "
            "assigned_at=COALESCE(assigned_at, datetime('now')) WHERE id=?",
            (staff["sub"], conv_id),
        )
        await conn.commit()
    _publish(conv_id, {"type": "mode_change", "to": "ai_draft", "by_staff_id": staff["sub"]})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/disable")
async def ai_draft_disable(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    await _require_assigned(conv_id, staff["sub"])
    await conv_dao.set_mode(conv_id, "ai", assigned_staff_id=None)
    _publish(conv_id, {"type": "mode_change", "to": "ai"})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/approve")
async def ai_draft_approve(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    """通过草稿：把最新草稿作为 assistant 消息发给用户。"""
    await _require_assigned(conv_id, staff["sub"])
    draft = await conv_dao.get_latest_ai_draft(conv_id)
    if draft is None:
        raise HTTPException(404, "no pending draft")
    await conv_dao.append_message(conv_id, role="assistant", content=draft)
    await conv_dao.clear_ai_drafts(conv_id)
    _publish(conv_id, {"type": "assistant_message", "content": draft})
    return {"ok": True}


class RewriteIn(BaseModel):
    rewrite: str


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/reject")
async def ai_draft_reject(
    conv_id: int, body: RewriteIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    """否决草稿：客服改写后以 human_agent 身份发给用户。"""
    await _require_assigned(conv_id, staff["sub"])
    await conv_dao.clear_ai_drafts(conv_id)
    await conv_dao.append_human_message(conv_id, staff["sub"], body.rewrite)
    _publish(
        conv_id,
        {"type": "human_message", "content": body.rewrite, "sender_staff_id": staff["sub"]},
    )
    return {"ok": True}


@router.get("/staff/api/v1/conversations/{conv_id}/stream")
async def stream(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> EventSourceResponse:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    _subscribers[conv_id].append(q)

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                ev = await q.get()
                yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        finally:
            _subscribers[conv_id].remove(q)

    return EventSourceResponse(gen())
