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
            yield se.sse_payload(
                se.EVENT_CONVERSATION,
                {
                    "conversation_id": conversation_id,
                    "user_type": "b",
                    "model": "claude-sonnet-4-6",
                },
            )
            yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
            async for ev in runtime.run_turn(
                conversation_id=conversation_id,
                user_type="b",
                subject_id=bu_id,
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
