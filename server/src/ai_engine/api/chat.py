import asyncio
import secrets
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from ai_engine.agent import runtime
from ai_engine.api import sse_events as se
from ai_engine.api.staff_conversations import publish_ai_draft, publish_user_message
from ai_engine.auth.bu_session import require_bu, resolve_identity
from ai_engine.persistence import conversations as conv_dao

router = APIRouter()

# conversation_id → asyncio.Event（用户点"停止生成"时 set，gen() 检测后退出）
_cancel_signals: dict[int, asyncio.Event] = {}


def _map_runtime_event(ev: dict[str, Any]) -> dict[str, str] | None:
    """把 runtime 的领域事件（text/tool_call/tool_result）映射到 spec §3.3 wire 事件。"""
    t = ev.get("type")
    if t == "text":
        return se.sse_payload(
            se.EVENT_CONTENT_BLOCK_DELTA,
            {"index": 0, "delta": {"type": "text_delta", "text": ev.get("text", "")}},
        )
    if t == "tool_call":
        return se.sse_payload(se.EVENT_TOOL_USE, {"name": ev.get("name"), "input": ev.get("input")})
    if t == "tool_result":
        return se.sse_payload(
            se.EVENT_TOOL_RESULT, {"name": ev.get("name"), "is_error": not ev.get("ok", False)}
        )
    if t == "system":  # 会话治理 / 成本治理等系统提示（spec §8）
        return se.sse_payload(se.EVENT_WARNING, {"text": ev.get("text", "")})
    return None


@router.get("/api/v1/chat")
async def chat(
    request: Request,
    conversation_id: int = Query(...),
    message: str = Query(...),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """SSE 主链路（两端：C 端 Bearer JWT / B 端 cookie）。Last-Event-ID 用于重连补推。"""
    user_type, subject_id = await resolve_identity(request)
    cancel_evt = asyncio.Event()
    _cancel_signals[conversation_id] = cancel_evt

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            yield se.sse_payload(
                se.EVENT_CONVERSATION,
                {
                    "conversation_id": conversation_id,
                    "user_type": user_type,
                    "model": "claude-sonnet-4-6",
                },
            )
            # spec §13：客服已接管 / 待接管时不调 AI，用户消息只入库 + 推给客服侧
            mode, _ = await conv_dao.get_mode(conversation_id)
            if mode in ("human_takeover", "human_pending"):
                await conv_dao.append_message(conversation_id, role="user", content=message)
                publish_user_message(conversation_id, message)
                yield se.sse_payload(se.EVENT_MODE_CHANGE, {"to": mode})
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "handed_to_human"})
                return

            if mode == "ai_draft":
                # spec §13.2：AI 出草稿不发用户，落库 + 推客服侧待 review
                draft = await runtime.collect_full_response(
                    conversation_id=conversation_id,
                    user_type=user_type,
                    subject_id=subject_id,
                    user_message=message,
                )
                await conv_dao.save_ai_draft(conversation_id, draft)
                publish_ai_draft(conversation_id, draft)
                yield se.sse_payload(se.EVENT_WARNING, {"text": "客服正在 review 您的回答…"})
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "ai_draft_pending"})
                return

            yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
            async for ev in runtime.run_turn(
                conversation_id=conversation_id,
                user_type=user_type,
                subject_id=subject_id,
                user_message=message,
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
async def cancel_stream(conversation_id: int, bu_id: str = Depends(require_bu)) -> None:
    """用户点"停止生成"。gen() 检测信号后 yield message_stop(cancelled) 并关闭流。"""
    evt = _cancel_signals.get(conversation_id)
    if evt:
        evt.set()
