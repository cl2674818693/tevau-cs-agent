import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from ai_engine.agent import runtime
from ai_engine.api import sse_events as se
from ai_engine.api.staff_conversations import (
    publish_ai_draft,
    publish_conversation_event,
    publish_user_message,
)
from ai_engine.auth.bu_session import USER_TYPE_GUEST, resolve_identity
from ai_engine.governance import rate_limit, token_budget
from ai_engine.persistence import conversations as conv_dao

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authorize_conversation(request: Request, conversation_id: int) -> tuple[str, str]:
    """解析身份并校验该会话归属当前调用者，防 IDOR 横向越权。返回 (user_type, subject_id)。"""
    user_type, subject_id = await resolve_identity(request)
    conv = await conv_dao.get_conversation(conversation_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")
    return user_type, subject_id


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
        return se.sse_payload(
            se.EVENT_TOOL_USE,
            {"tool_use_id": ev.get("id"), "name": ev.get("name"), "input": ev.get("input")},
        )
    if t == "tool_result":
        return se.sse_payload(
            se.EVENT_TOOL_RESULT,
            {
                "tool_use_id": ev.get("id"),
                "name": ev.get("name"),
                "is_error": not ev.get("ok", False),
            },
        )
    if t == "system":  # 会话治理 / 成本治理等系统提示（spec §8）
        return se.sse_payload(se.EVENT_WARNING, {"text": ev.get("text", "")})
    return None


def _spectator_event(ev: dict[str, Any]) -> dict[str, Any]:
    """把 runtime 事件转成旁观总线事件（assistant 文本改名以区分用户消息）。"""
    if ev.get("type") == "text":
        return {"type": "assistant_text", "content": ev.get("text", "")}
    return ev


@router.get("/api/v1/chat")
async def chat(
    request: Request,
    conversation_id: int = Query(...),
    message: str = Query(...),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """SSE 主链路（两端：C 端 Bearer JWT / B 端 cookie）。Last-Event-ID 用于重连补推。"""
    user_type, subject_id = await _authorize_conversation(request, conversation_id)
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
            # spec §6.4 兜底层：单 subject 每分钟消息数限流。
            # 游客 subject_id 由客户端 X-Guest-ID 决定（可伪造），故按客户端 IP 限流，防绕过刷量。
            rl_key = (
                f"g:ip:{request.client.host if request.client else 'anon'}"
                if user_type == USER_TYPE_GUEST
                else f"{user_type}:{subject_id}"
            )
            allowed, retry_after_ms = await rate_limit.check(rl_key)
            if not allowed:
                yield se.error_event(
                    "RATE_LIMITED", "消息过于频繁，请稍后再试。", retry_after_ms=retry_after_ms
                )
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "rate_limited"})
                return
            # spec §13：客服已接管 / 待接管时不调 AI，用户消息只入库 + 推给客服侧
            mode, _ = await conv_dao.get_mode(conversation_id)
            if mode in ("human_takeover", "human_pending"):
                await conv_dao.append_message(conversation_id, role="user", content=message)
                publish_user_message(conversation_id, message)
                yield se.sse_payload(se.EVENT_MODE_CHANGE, {"to": mode})
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "handed_to_human"})
                return

            # spec §8 成本治理入口硬闸：当日额度已用尽则不进 agent loop（省一次昂贵 LLM 调用）
            if await token_budget.is_exhausted(user_type, subject_id):
                yield se.sse_payload(
                    se.EVENT_WARNING,
                    {"text": "您今日的 AI 服务额度已用完，请明日再试，或点'转人工'。"},
                )
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "budget_exceeded"})
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
            publish_conversation_event(
                conversation_id, {"type": "user_message", "content": message}
            )
            async for ev in runtime.run_turn(
                conversation_id=conversation_id,
                user_type=user_type,
                subject_id=subject_id,
                user_message=message,
            ):
                if cancel_evt.is_set():
                    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "cancelled"})
                    return
                publish_conversation_event(conversation_id, _spectator_event(ev))
                mapped = _map_runtime_event(ev)
                if mapped is not None:
                    yield mapped
            yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "end_turn"})
        except Exception:  # 顶层兜底：记日志，对外只回固定文案，不外泄内部错误细节
            logger.exception("chat stream failed (conversation_id=%s)", conversation_id)
            yield se.error_event("INTERNAL_ERROR", "服务暂时不可用，请稍后再试。")
        finally:
            _cancel_signals.pop(conversation_id, None)

    return EventSourceResponse(gen(), ping=se.PING_INTERVAL_SECONDS)


@router.delete("/api/v1/chat/{conversation_id}/stream", status_code=204)
async def cancel_stream(conversation_id: int, request: Request) -> None:
    """用户点"停止生成"。gen() 检测信号后 yield message_stop(cancelled) 并关闭流。"""
    await _authorize_conversation(request, conversation_id)
    evt = _cancel_signals.get(conversation_id)
    if evt:
        evt.set()
