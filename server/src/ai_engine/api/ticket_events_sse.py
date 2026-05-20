import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ai_engine.api import sse_events as se
from ai_engine.api.staff_conversations import register_subscriber, unregister_subscriber
from ai_engine.auth.bu_session import resolve_identity
from ai_engine.persistence.conversations import get_conversation

router = APIRouter()

# 推给 C/B 端的工单生命周期事件（spec §7.2）
TICKET_EVENT_TYPES = {
    "ticket_event",
    "assigned",
    "in_progress",
    "escalated",
    "resolved",
    "closed",
    "reopen",
}


@router.get("/api/v1/conversations/{conv_id}/ticket-events-stream")
async def ticket_events_stream(conv_id: int, request: Request) -> EventSourceResponse:
    """SSE 长连：订阅该会话的工单状态事件（替换 MVP-2 轮询）。两端通用鉴权。"""
    user_type, subject_id = await resolve_identity(request)
    conv = await get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")

    q = register_subscriber(conv_id)

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                ev = await q.get()
                if ev.get("type") in TICKET_EVENT_TYPES:
                    yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        finally:
            unregister_subscriber(conv_id, q)

    return EventSourceResponse(gen(), ping=se.PING_INTERVAL_SECONDS)
