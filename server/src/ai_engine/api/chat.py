import asyncio
import contextlib
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
from ai_engine.config import settings
from ai_engine.governance import rate_limit, token_budget
from ai_engine.i18n import t as _t
from ai_engine.persistence import attachments as att_dao
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


async def _watch_disconnect(request: Request, cancel_evt: asyncio.Event) -> None:
    """周期性检测 client 是否断开；断开则 set cancel_evt 让 gen 链路立刻退出。

    sse_starlette 本身在 yield 时也会检测，但若 runtime 卡在 LLM 调用（非 yield 中），
    SSE 层察觉不到 client 已走 —— 这里 250ms 主动 poll 一次，覆盖该缝隙。
    用 wait_for(cancel_evt.wait()) 兼任"外部取消时立即退出"，避免空转 250ms。
    """
    try:
        while not cancel_evt.is_set():
            if await request.is_disconnected():
                cancel_evt.set()
                return
            try:
                await asyncio.wait_for(cancel_evt.wait(), timeout=0.25)
                return  # event set externally → exit immediately
            except asyncio.TimeoutError:
                pass
    except asyncio.CancelledError:
        pass


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
    if t == "error":  # runtime fail-soft 兜底（spec §3.3 错误码）
        return se.error_event(ev.get("code", "INTERNAL_ERROR"), ev.get("text", ""))
    return None


def _spectator_event(ev: dict[str, Any]) -> dict[str, Any]:
    """把 runtime 事件转成旁观总线事件（assistant 文本改名以区分用户消息）。"""
    if ev.get("type") == "text":
        return {"type": "assistant_text", "content": ev.get("text", "")}
    return ev


async def _replay_turn(conversation_id: int, turn_id: int) -> AsyncIterator[dict[str, str]]:
    """幂等重放：把某已完成回合的 assistant 文本按 SSE 帧重新流出，不调 LLM。"""
    yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
    for raw in await conv_dao.get_turn_assistant_texts(conversation_id, turn_id):
        yield se.sse_payload(
            se.EVENT_CONTENT_BLOCK_DELTA,
            {
                "index": 0,
                "delta": {"type": "text_delta", "text": runtime._history_text("assistant", raw)},
            },
        )
    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "replayed"})


async def _duplicate_turn_id(conversation_id: int, client_message_id: str | None) -> int | None:
    """幂等键命中已完成回合则返回其 turn_id，否则 None。"""
    if not client_message_id:
        return None
    prev = await conv_dao.find_completed_turn(conversation_id, client_message_id)
    return int(prev["id"]) if prev else None


def _parse_attachment_ids(raw: str | None) -> list[int]:
    """逗号分隔的 attachment_ids → int 列表，按上限截断，忽略非数字。"""
    if not raw:
        return []
    ids = [int(x) for x in raw.split(",") if x.strip().isdigit()]
    return ids[: settings.attachment_max_per_message]


async def _early_block(
    request: Request,
    user_type: str,
    subject_id: str,
    conversation_id: int,
    message: str,
    ui_locale: str | None,
) -> tuple[dict[str, str], str] | None:
    """入口护栏：rate_limit。返回 (error_frame, stop_reason) 或 None。"""
    rl_key = (
        f"g:ip:{request.client.host if request.client else 'anon'}"
        if user_type == USER_TYPE_GUEST
        else f"{user_type}:{subject_id}"
    )
    allowed, retry_after_ms = await rate_limit.check(rl_key)
    if not allowed:
        err = se.error_event(
            "RATE_LIMITED", _t("error.rate_limited", ui_locale), retry_after_ms=retry_after_ms
        )
        return err, "rate_limited"
    return None


async def _human_mode_turn(
    conversation_id: int,
    subject_id: str,
    mode: str,
    message: str,
    attachment_ids: list[int],
    ui_locale: str | None,
) -> AsyncIterator[dict[str, str]]:
    """spec §13：human_takeover / human_pending 时端点不调 AI，用户消息只入库 + 推客服侧。
    human_pending 额外 yield 一帧 warning ack：客服未上线时若不给即时回执，
    用户消息石沉大海会触发反复重发（见截图 conv=612 实例）。
    human_takeover 客服在线会回真消息，再加 ack 反而是噪音。"""
    mid = await conv_dao.append_message(conversation_id, role="user", content=message)
    bound = (
        await att_dao.bind_attachments(mid, conversation_id, subject_id, attachment_ids)
        if attachment_ids
        else []
    )
    publish_user_message(conversation_id, message, bound)
    if mode == "human_pending":
        yield se.sse_payload(
            se.EVENT_WARNING,
            {"text": _t("warning.handoff_message_recorded", ui_locale)},
        )
    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "handed_to_human"})


async def _stream_ai_turn(
    conversation_id: int,
    user_type: str,
    subject_id: str,
    message: str,
    client_message_id: str | None,
    cancel_evt: asyncio.Event,
    attachment_ids: list[int],
    ui_locale: str | None,
) -> AsyncIterator[dict[str, str]]:
    """正常 AI 回合：message_start → run_turn 事件映射 → message_stop。"""
    yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
    # 旁观客服可见用户发的图：把本轮附件 id/mime 一并推到旁观总线（绑定在 run_turn 内完成）
    spectator_atts = []
    for aid in attachment_ids:
        row = await att_dao.get_attachment(aid)
        if row and row["conversation_id"] == conversation_id:
            spectator_atts.append({"id": row["id"], "mime": row["mime"]})
    publish_conversation_event(
        conversation_id,
        {"type": "user_message", "content": message, "attachments": spectator_atts},
    )
    async for ev in runtime.run_turn(
        conversation_id=conversation_id,
        user_type=user_type,
        subject_id=subject_id,
        user_message=message,
        client_message_id=client_message_id,
        attachment_ids=attachment_ids,
        ui_locale=ui_locale,
    ):
        if cancel_evt.is_set():
            yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "cancelled"})
            return
        publish_conversation_event(conversation_id, _spectator_event(ev))
        mapped = _map_runtime_event(ev)
        if mapped is not None:
            yield mapped
    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "end_turn"})


@router.get("/api/v1/chat")
async def chat(  # noqa: C901 — 入口 dispatcher 本质，按 mode 分派到多条旁路（人工/草稿/AI）
    request: Request,
    conversation_id: int = Query(...),
    message: str = Query(...),
    client_message_id: str | None = Query(default=None),
    attachment_ids: str | None = Query(default=None),
    ui_locale: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> EventSourceResponse:
    """SSE 主链路（两端：C 端 Bearer JWT / B 端 cookie）。client_message_id 用于幂等重放。"""
    user_type, subject_id = await _authorize_conversation(request, conversation_id)
    att_ids = _parse_attachment_ids(attachment_ids)
    cancel_evt = asyncio.Event()
    _cancel_signals[conversation_id] = cancel_evt

    async def gen() -> AsyncIterator[dict[str, str]]:
        # 客户端 TCP 断开 → set cancel_evt → _stream_ai_turn 主动 return → runtime/LLM 上游级联关闭
        watcher = asyncio.create_task(_watch_disconnect(request, cancel_evt))
        try:
            yield se.sse_payload(
                se.EVENT_CONVERSATION,
                {
                    "conversation_id": conversation_id,
                    "user_type": user_type,
                    "model": "claude-sonnet-4-6",
                },
            )
            # 入口护栏：rate_limit
            blocked = await _early_block(
                request, user_type, subject_id, conversation_id, message, ui_locale
            )
            if blocked is not None:
                err_frame, stop_reason = blocked
                yield err_frame
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": stop_reason})
                return
            # 幂等：同一 client_message_id 已完成过则重放历史回复，不重复跑 LLM（防重连/重发刷量）
            dup_id = await _duplicate_turn_id(conversation_id, client_message_id)
            if dup_id is not None:
                async for frame in _replay_turn(conversation_id, dup_id):
                    yield frame
                return
            # spec §13：客服已接管 / 待接管时不调 AI，用户消息只入库 + 推给客服侧。
            # 不再 yield mode_change：当前 mode 已经稳定（不是"切换"），
            # 真正的 AI→human_pending 切换由 create_ticket 工具里的 _ensure_human_pending
            # 通过 publish_conversation_event 经常驻流广播一次，足够前端 setMode。
            # 这里再推一帧会让前端把这帧当成"新一次转人工"反复 push 系统提示，体感"任何消息都被转人工"。
            mode, _ = await conv_dao.get_mode(conversation_id)
            if mode in ("human_takeover", "human_pending"):
                async for frame in _human_mode_turn(
                    conversation_id, subject_id, mode, message, att_ids, ui_locale
                ):
                    yield frame
                return

            # spec §8 成本治理入口硬闸：当日额度已用尽则不进 agent loop（省一次昂贵 LLM 调用）
            if await token_budget.is_exhausted(user_type, subject_id):
                yield se.sse_payload(
                    se.EVENT_WARNING,
                    {"text": _t("warning.budget_exhausted", ui_locale)},
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
                yield se.sse_payload(se.EVENT_WARNING, {"text": _t("warning.draft_review", ui_locale)})
                yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "ai_draft_pending"})
                return

            async for frame in _stream_ai_turn(
                conversation_id,
                user_type,
                subject_id,
                message,
                client_message_id,
                cancel_evt,
                att_ids,
                ui_locale,
            ):
                yield frame
        except Exception:  # 顶层兜底：记日志，对外只回固定文案，不外泄内部错误细节
            logger.exception("chat stream failed (conversation_id=%s)", conversation_id)
            yield se.error_event("INTERNAL_ERROR", _t("error.internal", ui_locale))
        finally:
            cancel_evt.set()  # 兜底：gen 退出时确保下游协程能看到取消信号
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
            _cancel_signals.pop(conversation_id, None)

    return EventSourceResponse(gen(), ping=se.PING_INTERVAL_SECONDS)


@router.delete("/api/v1/chat/{conversation_id}/stream", status_code=204)
async def cancel_stream(conversation_id: int, request: Request) -> None:
    """用户点"停止生成"。gen() 检测信号后 yield message_stop(cancelled) 并关闭流。"""
    await _authorize_conversation(request, conversation_id)
    evt = _cancel_signals.get(conversation_id)
    if evt:
        evt.set()
