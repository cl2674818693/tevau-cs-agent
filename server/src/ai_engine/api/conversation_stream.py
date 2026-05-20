import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ai_engine.api import sse_events as se
from ai_engine.api.staff_conversations import register_subscriber, unregister_subscriber
from ai_engine.auth.bu_session import resolve_identity
from ai_engine.persistence.conversations import get_conversation

router = APIRouter()

# 客服 → 用户方向的事件（用户侧常驻流转发；不含 user_message/ai_draft_ready/旁观事件）
USER_FACING_EVENTS = {
    "human_message",  # 客服接管后的回复
    "assistant_message",  # ai_draft 审核通过后发出的草稿
    "mode_change",  # 接管 / 释放 / 转 ai_draft，让前端切 UI
    "transferred",  # 转派
    "request_human",  # 已为你请求人工
}


@router.get("/api/v1/conversations/{conv_id}/messages-stream")
async def messages_stream(conv_id: int, request: Request) -> EventSourceResponse:
    """用户侧常驻 SSE：接收客服回复 / 审核通过的草稿 / 模式变更（spec §13）。两端通用鉴权。"""
    user_type, subject_id = await resolve_identity(request)
    conv = await get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")

    q = register_subscriber(conv_id)

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                ev = await q.get()
                if ev.get("type") in USER_FACING_EVENTS:
                    yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        finally:
            unregister_subscriber(conv_id, q)

    return EventSourceResponse(gen(), ping=se.PING_INTERVAL_SECONDS)
