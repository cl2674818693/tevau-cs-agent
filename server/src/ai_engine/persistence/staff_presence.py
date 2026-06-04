"""客服在线状态：心跳 upsert + 后台查询。"""

from datetime import UTC, datetime, timedelta
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def heartbeat(staff_id: str, status: str = "online") -> None:
    """心跳：upsert (staff_id, status, last_seen_at=now)。"""
    await db.execute(
        "INSERT INTO staff_presence(staff_id, status, last_seen_at) "
        "VALUES (:sid, :s, :now) "
        "ON CONFLICT(staff_id) DO UPDATE SET "
        "status = excluded.status, last_seen_at = excluded.last_seen_at",
        {"sid": staff_id, "s": status, "now": now_str()},
    )


async def set_offline(staff_id: str) -> None:
    await db.execute(
        "UPDATE staff_presence SET status = 'offline' WHERE staff_id = :sid",
        {"sid": staff_id},
    )


async def list_all() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT staff_id, status, last_seen_at FROM staff_presence ORDER BY staff_id"
    )


async def list_active(
    window_seconds: int = 300, on_shift_only: bool = False
) -> list[dict[str, Any]]:
    """返回当前 status != offline 且 last_seen_at 在窗口内的客服。

    M4: on_shift_only=True 时进一步过滤"当前在班"（与 staff_shifts 表 JOIN）。
    """
    cutoff = (datetime.now(UTC) - timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    if not on_shift_only:
        return await db.fetch_all(
            "SELECT staff_id, status, last_seen_at FROM staff_presence "
            "WHERE status != 'offline' AND last_seen_at >= :cutoff ORDER BY staff_id",
            {"cutoff": cutoff},
        )
    now_ts = (datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S")
    return await db.fetch_all(
        "SELECT p.staff_id, p.status, p.last_seen_at FROM staff_presence p "
        "WHERE p.status != 'offline' AND p.last_seen_at >= :cutoff "
        "AND EXISTS (SELECT 1 FROM staff_shifts s WHERE s.staff_id = p.staff_id "
        "AND s.start_at <= :now AND s.end_at >= :now) "
        "ORDER BY p.staff_id",
        {"cutoff": cutoff, "now": now_ts},
    )


async def release_pending_assignments(staff_id: str) -> list[int]:
    """关在线开关时释放：把当前 mode=human_pending 且派给该 staff 的会话清回开放池。
    已 human_takeover 的会话不动（允许聊完）。返回被释放的 conv_id 列表，给调用方推 SSE 用。

    SQLite 不支持 UPDATE...RETURNING（3.35 之前），用 SELECT→UPDATE 两步走，跨 PG/SQLite 都稳。
    并发安全：两步之间另一线程可能新派给该 staff，那次新派会在下一次开关切换时被收掉，
    不需要事务包裹（worst case 是一次派单短暂悬空，可接受）。
    """
    rows = await db.fetch_all(
        "SELECT id FROM conversations "
        "WHERE assigned_staff_id=:sid AND mode='human_pending'",
        {"sid": staff_id},
    )
    ids = [int(r["id"]) for r in rows]
    if not ids:
        return []
    placeholders = ",".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": v for i, v in enumerate(ids)}
    params["sid"] = staff_id
    await db.execute(
        f"UPDATE conversations SET assigned_staff_id=NULL, assigned_at=NULL "
        f"WHERE id IN ({placeholders}) AND assigned_staff_id=:sid AND mode='human_pending'",
        params,
    )
    return ids
