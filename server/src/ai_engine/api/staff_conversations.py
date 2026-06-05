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
from ai_engine.utils.text_sanitize import sanitize_user_text

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
    """B-P1-2: 跨副本事件总线 publish 的退避重试。

    单次失败就丢消息会让多副本部署下的客服 SSE 偶发丢核心事件（user_message /
    mode_change / human_message 等）。按 50/150/300ms 退避重试 3 次，仍失败仅 log
    不阻断主链路（本进程订阅者已先行本地投递，不受 Redis 影响）。
    与 chat.signal_cancel 的重试策略对齐。
    """
    client = _get_redis()
    if client is None:
        return
    channel = f"conv:{conv_id}"
    payload = json.dumps({"o": _PROC_ID, "c": conv_id, "e": event}, ensure_ascii=False)
    delays = (0.05, 0.15, 0.3)
    for i, delay in enumerate(delays):
        try:
            await client.publish(channel, payload)
            return
        except Exception:
            if i + 1 >= len(delays):
                logger.warning(
                    "conversation bus redis publish failed after retries", exc_info=True
                )
                return
            await asyncio.sleep(delay)


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


async def _human_message_event(
    staff_sub: str, content: str, attachments: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """构造 human_message 事件，带 display_name（用户侧客服署名）；查不到时回退 staff_id。"""
    staff = await get_staff(staff_sub)
    display_name = staff["display_name"] if staff else staff_sub
    return {
        "type": "human_message",
        "content": content,
        "sender_staff_id": staff_sub,
        "display_name": display_name,
        "attachments": [{"id": a["id"], "mime": a["mime"]} for a in (attachments or [])],
    }


def publish_user_message(
    conv_id: int, content: str, attachments: list[dict[str, Any]] | None = None
) -> None:
    """human_takeover/pending 时，chat 端点把用户消息推到订阅该会话的客服侧。"""
    _publish(
        conv_id,
        {
            "type": "user_message",
            "content": content,
            "attachments": [{"id": a["id"], "mime": a["mime"]} for a in (attachments or [])],
        },
    )


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
    return await conv_dao.list_for_staff(status, risk_only=risk_only, me=str(staff["sub"]))


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
                "assigned_at=:now WHERE id=:id AND "
                "(assigned_staff_id IS NULL OR assigned_staff_id=:sub)"
            ),
            {"sub": staff["sub"], "now": now_str(), "id": conv_id},
        )
        if cur.rowcount == 0:
            raise HTTPException(409, "already taken by another staff")
    await log_staff_action(conv_id, staff["sub"], "take")
    metrics.staff_takeovers.labels(staff_id=staff["sub"]).inc()
    await refresh_human_pending()
    _publish(conv_id, {"type": "mode_change", "to": "human_takeover", "by_staff_id": staff["sub"]})
    # B-P0-8: 中断 conv_id 上仍在跑的 AI 流，防止 mode 已切走但 AI 仍在写 assistant 消息
    from ai_engine.api.chat import signal_cancel  # lazy import 避免循环

    await signal_cancel(conv_id)
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


@router.get("/staff/api/v1/transfer-candidates")
async def transfer_candidates(
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """转派目标候选：返回所有 active 客服（除自己）的 staff_id/display_name/role。
    后端按调用方 role 过滤候选范围与现有 transfer_to 端点的鉴权规则保持一致：
    agent 仅看 engineer；senior/engineer/admin 看全部。"""
    from ai_engine.persistence.staff import list_staff

    me = staff["sub"]
    my_role = staff.get("role")
    rows = await list_staff()
    active = [r for r in rows if int(r["active"]) == 1 and r["staff_id"] != me]
    if my_role == "agent":
        active = [r for r in active if r["role"] == "engineer"]
    return {
        "candidates": [
            {
                "staff_id": r["staff_id"],
                "display_name": r["display_name"],
                "role": r["role"],
            }
            for r in active
        ]
    }


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
    # B-P0-8: 转派也代表当前会话被人接管，中断仍在跑的 AI 流
    from ai_engine.api.chat import signal_cancel  # lazy import 避免循环

    await signal_cancel(conv_id)
    return {"ok": True}


class StaffMsgIn(BaseModel):
    content: str = ""
    attachment_ids: list[int] = []


@router.post("/staff/api/v1/conversations/{conv_id}/messages")
async def send_message(
    conv_id: int, body: StaffMsgIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    mode, sid = await conv_dao.get_mode(conv_id)
    if mode != "human_takeover" or sid != staff["sub"]:
        raise HTTPException(403, "not your conversation")
    # B-P2-5: 先 sanitize 再空校验；避免零宽字符消息绕过 strip
    content = sanitize_user_text(body.content)
    if not content.strip() and not body.attachment_ids:
        raise HTTPException(422, "empty message")
    mid = await conv_dao.append_human_message(conv_id, staff["sub"], content)
    from ai_engine.persistence import attachments as att_dao

    bound = (
        await att_dao.bind_attachments(mid, conv_id, staff["sub"], body.attachment_ids)
        if body.attachment_ids
        else []
    )
    _publish(conv_id, await _human_message_event(staff["sub"], content, bound))
    return {"ok": True}


async def _require_assigned(conv_id: int, staff_sub: str) -> None:
    _, sid = await conv_dao.get_mode(conv_id)
    if sid != staff_sub:
        raise HTTPException(403, "not your conversation")


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
async def ai_draft_enable(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    """切到 ai_draft：AI 出草稿、客服 review 后发。

    安全语义（B-P0-1 / B-P1-10）：
    - 未指派 / 本人已指派 → 200，接管并切 ai_draft（与原行为一致）；
    - 他人已接管 → 409（与 take/transfer 一致的反抢占模型）；
    - conversation 不存在 → 404（避免返回 ok=True 帮攻击者枚举会话 ID）。
    UPDATE WHERE 与 take 同款 CAS：assigned_staff_id IS NULL OR =:sub，rowcount=0 后用
    二次 SELECT 区分 404/409，避免"先查后改"的 race。
    """
    async with get_conn() as conn:
        cur = await conn.execute(
            text(
                "UPDATE conversations SET mode='ai_draft', assigned_staff_id=:sub, "
                "assigned_at=COALESCE(assigned_at, :now) WHERE id=:id AND "
                "(assigned_staff_id IS NULL OR assigned_staff_id=:sub)"
            ),
            {"sub": staff["sub"], "now": now_str(), "id": conv_id},
        )
        if cur.rowcount == 0:
            res = await conn.execute(
                text("SELECT 1 FROM conversations WHERE id=:id"), {"id": conv_id}
            )
            if res.first() is None:
                raise HTTPException(404, "conversation not found")
            raise HTTPException(409, "already taken by another staff")
    await refresh_human_pending()
    _publish(conv_id, {"type": "mode_change", "to": "ai_draft", "by_staff_id": staff["sub"]})
    # B-P0-8: enable 把 mode 切去 ai_draft，仍在跑的"AI 直接发用户"流也要中断
    from ai_engine.api.chat import signal_cancel  # lazy import 避免循环

    await signal_cancel(conv_id)
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
    """通过草稿：把最新草稿作为 assistant 消息发给用户。

    B-P1-9 并发幂等：用 DELETE WHERE id=:draft_id 单条删除作为 CAS。两次并发 approve
    只有一个 rowcount=1 拿到 draft 内容；另一个 rowcount=0 → 404（草稿已被消费）。
    防"网络抖动 / 前端双击" 导致同一段草稿连发两次 assistant 消息。
    """
    await _require_assigned(conv_id, staff["sub"])
    async with get_conn() as conn:
        res = await conn.execute(
            text(
                "SELECT id, content FROM messages WHERE conversation_id=:id "
                "AND role='ai_draft' ORDER BY id DESC LIMIT 1"
            ),
            {"id": conv_id},
        )
        row = res.first()
        if row is None:
            raise HTTPException(404, "no pending draft")
        draft_id, draft_content = row[0], row[1]
        cur = await conn.execute(
            text("DELETE FROM messages WHERE id=:id AND role='ai_draft'"),
            {"id": draft_id},
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "no pending draft")
        # 防御性：同 conv 下若还有其他 ai_draft 行（理论应只一条），一并清除
        await conn.execute(
            text(
                "DELETE FROM messages WHERE conversation_id=:id AND role='ai_draft'"
            ),
            {"id": conv_id},
        )
        await conn.execute(
            text(
                "INSERT INTO messages(conversation_id, role, content, created_at) "
                "VALUES (:cid, 'assistant', :c, :now)"
            ),
            {"cid": conv_id, "c": draft_content, "now": now_str()},
        )
    _publish(conv_id, {"type": "assistant_message", "content": draft_content})
    return {"ok": True}


class RewriteIn(BaseModel):
    rewrite: str


@router.post("/staff/api/v1/conversations/{conv_id}/ai-draft/reject")
async def ai_draft_reject(
    conv_id: int, body: RewriteIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, bool]:
    """否决草稿：客服改写后以 human_agent 身份发给用户。"""
    await _require_assigned(conv_id, staff["sub"])
    # 与 approve 对齐：草稿不存在时拒绝，避免前端误触/重复点击时把同一段改写写两次
    draft = await conv_dao.get_latest_ai_draft(conv_id)
    if draft is None:
        raise HTTPException(404, "no pending draft")
    # B-P2-5: sanitize rewrite，并防被全零宽字符的 rewrite 绕过有效性
    rewrite = sanitize_user_text(body.rewrite)
    if not rewrite.strip():
        raise HTTPException(422, "rewrite must not be empty")
    await conv_dao.clear_ai_drafts(conv_id)
    await conv_dao.append_human_message(conv_id, staff["sub"], rewrite)
    _publish(conv_id, await _human_message_event(staff["sub"], rewrite))
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


class AiToolIn(BaseModel):
    params: dict[str, Any] = {}


@router.post("/staff/api/v1/conversations/{conv_id}/ai-tools/{tool_name}")
async def run_ai_tool(
    conv_id: int,
    tool_name: str,
    body: AiToolIn,
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """客服代查 AI 工具：强制以该会话身份调用（不能跨用户），结果仅返回客服、不进对话流。

    归属校验（B-P0-2）：仅 senior/engineer 可调；且会话必须未指派或本人已接管。
    他人已接管时 403，防止通过改 conv_id 越权代查别的客服的客户隐私数据。
    """
    if staff.get("role") not in ("senior", "engineer"):
        raise HTTPException(403, "ai-tools requires senior/engineer")
    conv = await conv_dao.get_conversation_meta(conv_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    assigned = conv.get("assigned_staff_id")
    if assigned is not None and assigned != staff["sub"]:
        raise HTTPException(403, "conversation assigned to another staff")
    # B-P1-18: 兜底外层超时，防业务库/LLM 工具卡死把 HTTP 连接吊起
    try:
        return await asyncio.wait_for(
            # senior/engineer 代查时给明文（spec §13.3）；工具白名单/角色细粒度策略已下线。
            dispatch(
                tool_name=tool_name,
                params=body.params,
                user_type=str(conv["user_type"]),
                subject_id=str(conv["subject_id"]),
                conversation_id=conv_id,
                unmask=True,
            ),
            timeout=settings.tool_dispatch_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "tool dispatch timed out") from exc


@router.get("/staff/api/v1/conversations/{conv_id}/spectate-stream")
async def spectate_stream(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> EventSourceResponse:
    """旁观（不接管）：仅 senior/engineer 可订阅 AI 处理过程。"""
    if staff.get("role") not in ("senior", "engineer"):
        raise HTTPException(403, "spectate requires senior/engineer")
    return _subscribe(conv_id)
