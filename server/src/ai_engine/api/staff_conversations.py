import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from ai_engine.agent.tool_router import dispatch
from ai_engine.auth.staff_session import require_staff
from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import get_conn
from ai_engine.persistence.schema import now_str
from ai_engine.persistence.staff import get_staff
from ai_engine.persistence.staff_metrics import log_staff_action, refresh_human_pending

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

router = APIRouter()

# 会话事件订阅总线。进程内用内存队列；配置 REDIS_URL 时再叠加 Redis pub/sub 做跨副本广播：
#   - 核心 user↔staff 事件（_publish：human_message/mode_change/transferred/assistant_message/
#     user_message/ai_draft_ready/ticket_event/request_human）跨副本可达；
#   - 旁观高频 firehose（publish_conversation_event）保持本进程内（spectate 为内部观测，
#     不保证跨副本，避免每个 runtime 事件都打 Redis）。
# 去重：每条 Redis 消息带本进程 _PROC_ID，桥接收到自己发的消息会跳过（本地已投递）。
_subscribers: dict[int, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
_PROC_ID = uuid.uuid4().hex
_redis: "Redis | None" = None
_bridge_task: "asyncio.Task[None] | None" = None
_publish_tasks: set[asyncio.Task[None]] = set()  # 持有 fire-and-forget 任务引用，防被 GC


def _get_redis() -> "Redis | None":
    global _redis
    if not settings.redis_url:
        return None
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _deliver_local(conv_id: int, event: dict[str, Any]) -> None:
    for q in _subscribers.get(conv_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def _redis_publish(conv_id: int, event: dict[str, Any]) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        await client.publish(
            f"conv:{conv_id}",
            json.dumps({"o": _PROC_ID, "c": conv_id, "e": event}, ensure_ascii=False),
        )
    except Exception:  # redis 故障不阻断主链路；本进程订阅者已本地投递
        logger.warning("conversation bus redis publish failed", exc_info=True)


def _publish(conv_id: int, event: dict[str, Any]) -> None:
    """投递核心会话事件：本进程订阅者立即收到；配置 Redis 时跨副本广播给其他进程。"""
    _deliver_local(conv_id, event)
    if _get_redis() is not None:
        try:
            task = asyncio.get_running_loop().create_task(_redis_publish(conv_id, event))
            _publish_tasks.add(task)
            task.add_done_callback(_publish_tasks.discard)
        except RuntimeError:  # 无运行中的事件循环（_publish 均在请求内调用，理论上不发生）
            logger.warning("conversation bus _publish outside event loop", exc_info=True)


async def _redis_bridge() -> None:
    """进程级 Redis 订阅：把其他副本发布的会话事件 fan-out 到本进程本地队列。"""
    client = _get_redis()
    if client is None:
        return
    pubsub = client.pubsub()
    await pubsub.psubscribe("conv:*")
    async for msg in pubsub.listen():
        if msg.get("type") != "pmessage":
            continue
        try:
            payload = json.loads(msg["data"])
            if payload.get("o") == _PROC_ID:  # 本进程发的已本地投递，跳过避免双发
                continue
            _deliver_local(int(payload["c"]), payload["e"])
        except (ValueError, KeyError, TypeError):
            logger.warning("conversation bus bridge bad message", exc_info=True)


async def start_redis_bridge() -> None:
    """应用启动时调用：配置 Redis 时拉起进程级订阅桥（多副本实时事件互通）。"""
    global _bridge_task
    if _get_redis() is not None and _bridge_task is None:
        _bridge_task = asyncio.create_task(_redis_bridge())


async def _human_message_event(staff_sub: str, content: str) -> dict[str, Any]:
    """构造 human_message 事件，带 display_name（用户侧客服署名）；查不到时回退 staff_id。"""
    staff = await get_staff(staff_sub)
    display_name = staff["display_name"] if staff else staff_sub
    return {
        "type": "human_message",
        "content": content,
        "sender_staff_id": staff_sub,
        "display_name": display_name,
    }


def publish_user_message(conv_id: int, content: str) -> None:
    """human_takeover/pending 时，chat 端点把用户消息推到订阅该会话的客服侧。"""
    _publish(conv_id, {"type": "user_message", "content": content})


def publish_ai_draft(conv_id: int, draft: str) -> None:
    """ai_draft 模式：AI 草稿推到客服侧待 review。"""
    _publish(conv_id, {"type": "ai_draft_ready", "draft": draft})


def publish_conversation_event(conv_id: int, event: dict[str, Any]) -> None:
    """把会话事件推到订阅总线（旁观客服可见 AI 处理过程）。无订阅者时近乎零成本。"""
    if _subscribers.get(conv_id):
        _publish(conv_id, event)


@router.get("/staff/api/v1/conversations")
async def list_conversations(
    status: str = Query("human_pending"),
    risk_only: bool = Query(False),
    staff: dict[str, Any] = Depends(require_staff),
) -> list[dict[str, object]]:
    return await conv_dao.list_for_staff(status, risk_only=risk_only)


@router.get("/staff/api/v1/conversations/{conv_id}")
async def get_one(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, object]:
    """单会话元信息：前端详情页据此初始化接管态（刷新后已接管会话仍能继续回复）。"""
    conv = await conv_dao.get_conversation_meta(conv_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    return conv


@router.post("/staff/api/v1/conversations/{conv_id}/take")
async def take(conv_id: int, staff: dict[str, Any] = Depends(require_staff)) -> dict[str, bool]:
    # 原子接管：仅 assigned_staff_id IS NULL 时才更新（防多客服抢同一会话）
    async with get_conn() as conn:
        cur = await conn.execute(
            text(
                "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:sub, "
                "assigned_at=:now WHERE id=:id AND assigned_staff_id IS NULL"
            ),
            {"sub": staff["sub"], "now": now_str(), "id": conv_id},
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "already taken by another staff")
    await log_staff_action(conv_id, staff["sub"], "take")
    metrics.staff_takeovers.labels(staff_id=staff["sub"]).inc()
    await refresh_human_pending()
    _publish(conv_id, {"type": "mode_change", "to": "human_takeover", "by_staff_id": staff["sub"]})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/release")
async def release(conv_id: int, staff: dict[str, Any] = Depends(require_staff)) -> dict[str, bool]:
    async with get_conn() as conn:
        cur = await conn.execute(
            text(
                "UPDATE conversations SET mode='ai', assigned_staff_id=NULL, assigned_at=NULL "
                "WHERE id=:id AND assigned_staff_id=:sub"
            ),
            {"id": conv_id, "sub": staff["sub"]},
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "not assigned to you")
    await log_staff_action(conv_id, staff["sub"], "release")
    _publish(conv_id, {"type": "mode_change", "to": "ai"})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/resolve")
async def resolve(conv_id: int, staff: dict[str, Any] = Depends(require_staff)) -> dict[str, bool]:
    """客服标记已解决：释放回 AI 并记 resolved（用于 KPI 解决率）。"""
    async with get_conn() as conn:
        cur = await conn.execute(
            text(
                "UPDATE conversations SET mode='ai', assigned_staff_id=NULL, assigned_at=NULL "
                "WHERE id=:id AND assigned_staff_id=:sub"
            ),
            {"id": conv_id, "sub": staff["sub"]},
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "not assigned to you")
    await log_staff_action(conv_id, staff["sub"], "resolved")
    _publish(conv_id, {"type": "mode_change", "to": "ai", "resolved": True})
    return {"ok": True}


@router.post("/staff/api/v1/conversations/{conv_id}/transfer-to/{target_staff_id}")
async def transfer_to(
    conv_id: int,
    target_staff_id: str,
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, bool]:
    """转派：当前 staff 释放并直接分给目标。agent 只能转 engineer；senior/engineer 可转任意。"""
    target = await get_staff(target_staff_id)
    if target is None or int(target["active"]) != 1:
        raise HTTPException(404, "target staff not found")
    if staff.get("role") == "agent" and target["role"] != "engineer":
        raise HTTPException(403, "agent can only transfer to engineer")
    async with get_conn() as conn:
        cur = await conn.execute(
            text(
                "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:target, "
                "assigned_at=:now WHERE id=:id AND assigned_staff_id=:sub"
            ),
            {"target": target_staff_id, "now": now_str(), "id": conv_id, "sub": staff["sub"]},
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "not assigned to you")
    await log_staff_action(conv_id, staff["sub"], "transfer_out")
    await log_staff_action(conv_id, target_staff_id, "take")
    _publish(conv_id, {"type": "transferred", "to_staff_id": target_staff_id})
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
    _publish(conv_id, await _human_message_event(staff["sub"], body.content))
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
            text(
                "UPDATE conversations SET mode='ai_draft', assigned_staff_id=:sub, "
                "assigned_at=COALESCE(assigned_at, :now) WHERE id=:id"
            ),
            {"sub": staff["sub"], "now": now_str(), "id": conv_id},
        )
    await refresh_human_pending()
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
    _publish(conv_id, await _human_message_event(staff["sub"], body.rewrite))
    return {"ok": True}


def register_subscriber(conv_id: int) -> asyncio.Queue[dict[str, Any]]:
    """注册一个会话事件订阅队列（调用方负责 unregister）。"""
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    _subscribers[conv_id].append(q)
    return q


def unregister_subscriber(conv_id: int, q: asyncio.Queue[dict[str, Any]]) -> None:
    if q in _subscribers.get(conv_id, []):
        _subscribers[conv_id].remove(q)


def _subscribe(conv_id: int) -> EventSourceResponse:
    q = register_subscriber(conv_id)

    async def gen() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                ev = await q.get()
                yield {"event": ev["type"], "data": json.dumps(ev, ensure_ascii=False)}
        finally:
            unregister_subscriber(conv_id, q)

    return EventSourceResponse(gen())


@router.get("/staff/api/v1/conversations/{conv_id}/stream")
async def stream(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> EventSourceResponse:
    return _subscribe(conv_id)


_STAFF_TOOL_WHITELIST = {
    "query_user",
    "query_card",
    "query_kyc",
    "query_balance",
    "query_transaction",
    "query_bu_order",
    "query_bu_request_log",
    "search_code",
    "lookup_api_doc",
    "read_file",
}


class AiToolIn(BaseModel):
    params: dict[str, Any] = {}


@router.post("/staff/api/v1/conversations/{conv_id}/ai-tools/{tool_name}")
async def run_ai_tool(
    conv_id: int,
    tool_name: str,
    body: AiToolIn,
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """客服代查 AI 工具：强制以该会话身份调用（不能跨用户），结果仅返回客服、不进对话流。"""
    if staff.get("role") not in ("senior", "engineer"):
        raise HTTPException(403, "ai-tools requires senior/engineer")
    if tool_name not in _STAFF_TOOL_WHITELIST:
        raise HTTPException(400, f"tool not allowed: {tool_name}")
    conv = await conv_dao.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    # spec §13.3：仅 engineer 可解锁部分脱敏；senior 看脱敏结果
    return await dispatch(
        tool_name=tool_name,
        params=body.params,
        user_type=str(conv["user_type"]),
        subject_id=str(conv["subject_id"]),
        conversation_id=conv_id,
        unmask=(staff.get("role") == "engineer"),
    )


@router.get("/staff/api/v1/conversations/{conv_id}/spectate-stream")
async def spectate_stream(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> EventSourceResponse:
    """旁观（不接管）：仅 senior/engineer 可订阅 AI 处理过程。"""
    if staff.get("role") not in ("senior", "engineer"):
        raise HTTPException(403, "spectate requires senior/engineer")
    return _subscribe(conv_id)
