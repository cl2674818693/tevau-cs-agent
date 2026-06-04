"""转人工派单 service：服务端"最少在聊"派单 + 60s 超时回退池。

替代原 shifts_query 班外判断模型。两个调用入口：
  1. api/user_events.py::request_human（C 端用户主动转人工）
  2. agent/tools/create_ticket.py::_ensure_human_pending（AI 工具触发）

派给某人后客服侧 SSE 推 conversation_assigned；60s 内未 take 则后台 watcher
清空 assigned_staff_id → 推 conversation_assignment_cleared 让所有 online 客服可抢。
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from ai_engine.persistence import db, rbac
from ai_engine.persistence.schema import now_str

logger = logging.getLogger(__name__)

_HEARTBEAT_WINDOW_SECONDS = 300


async def _roles_with_chat_dispatch() -> list[str]:
    matrix = await rbac.list_matrix()
    return [role for role, perms in matrix.items() if perms.get("chat.dispatch")]


async def _pick_least_loaded(roles: list[str]) -> str | None:
    if not roles:
        return None
    cutoff = (datetime.now(UTC) - timedelta(seconds=_HEARTBEAT_WINDOW_SECONDS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    role_placeholders = ",".join(f":r{i}" for i in range(len(roles)))
    params: dict[str, object] = {"cutoff": cutoff}
    for i, r in enumerate(roles):
        params[f"r{i}"] = r

    row = await db.fetch_one(
        f"""
        SELECT p.staff_id,
               (SELECT COUNT(*) FROM conversations c
                WHERE c.assigned_staff_id=p.staff_id
                  AND c.mode IN ('human_takeover','human_pending')) AS load
          FROM staff_presence p
          JOIN staff s ON s.staff_id = p.staff_id
         WHERE p.status='online'
           AND p.last_seen_at >= :cutoff
           AND s.role IN ({role_placeholders})
         ORDER BY load ASC, p.last_seen_at ASC
         LIMIT 1
        """,
        params,
    )
    return str(row["staff_id"]) if row else None


async def dispatch_to_human_pending(conv_id: int) -> dict:
    """转人工时按"最少在聊"派单。
    返回:
      {dispatched: True, staff_id: X, no_one_online: False}      —— 成功派给某人
      {dispatched: False, no_one_online: True}                   —— 全员 offline / 全无权限
      {dispatched: False, already_assigned: True}                —— 并发：上一次调用已派
    """
    roles = await _roles_with_chat_dispatch()
    picked = await _pick_least_loaded(roles)
    if not picked:
        return {"dispatched": False, "no_one_online": True}

    await db.execute(
        "UPDATE conversations SET assigned_staff_id=:sid, assigned_at=:now "
        "WHERE id=:id AND mode='human_pending' AND assigned_staff_id IS NULL",
        {"sid": picked, "now": now_str(), "id": conv_id},
    )
    row = await db.fetch_one(
        "SELECT assigned_staff_id FROM conversations WHERE id=:id", {"id": conv_id}
    )
    if not row or str(row["assigned_staff_id"] or "") != picked:
        return {"dispatched": False, "already_assigned": True}

    from ai_engine.api.staff_conversations import publish_conversation_event

    publish_conversation_event(conv_id, {"type": "conversation_assigned", "staff_id": picked})

    return {"dispatched": True, "staff_id": picked, "no_one_online": False}


_TIMEOUT_SECONDS = 60
_WATCHER_INTERVAL_SECONDS = 10


async def _scan_and_clear_timeouts() -> list[int]:
    """扫一遍超时的 human_pending 派单，清回开放池。返回被清空的 conv_id 列表。"""
    cutoff = (datetime.now(UTC) - timedelta(seconds=_TIMEOUT_SECONDS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    rows = await db.fetch_all(
        "SELECT id FROM conversations "
        "WHERE mode='human_pending' "
        "  AND assigned_staff_id IS NOT NULL "
        "  AND assigned_at < :cutoff",
        {"cutoff": cutoff},
    )
    ids = [int(r["id"]) for r in rows]
    if not ids:
        return []
    placeholders = ",".join(f":id{i}" for i in range(len(ids)))
    params: dict[str, object] = {"cutoff": cutoff}
    for i, v in enumerate(ids):
        params[f"id{i}"] = v
    await db.execute(
        f"UPDATE conversations SET assigned_staff_id=NULL, assigned_at=NULL "
        f"WHERE id IN ({placeholders}) "
        f"  AND mode='human_pending' "
        f"  AND assigned_at < :cutoff",
        params,
    )
    return ids


async def _watcher_loop() -> None:
    """常驻协程：每 10 秒扫一遍，超时派单回开放池 + SSE 推所有相关订阅者。"""
    from ai_engine.api.staff_conversations import publish_conversation_event

    while True:
        try:
            cleared = await _scan_and_clear_timeouts()
            for cid in cleared:
                publish_conversation_event(cid, {"type": "conversation_assignment_cleared"})
        except Exception:
            logger.exception("dispatch watcher iteration failed")
        await asyncio.sleep(_WATCHER_INTERVAL_SECONDS)


def start_watcher() -> asyncio.Task:
    """在 FastAPI lifespan startup 中调一次。返回 Task 便于关闭时 cancel。"""
    return asyncio.create_task(_watcher_loop(), name="dispatch_watcher")
