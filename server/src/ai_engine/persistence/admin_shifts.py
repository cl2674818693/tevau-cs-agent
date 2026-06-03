"""排班 CRUD + 按客服/时间范围查询。"""

from datetime import datetime
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


def _parse_iso(s: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid {field} (ISO 8601 required): {s!r}") from e


async def create_shift(staff_id: str, start_at: str, end_at: str) -> int:
    sa = _parse_iso(start_at, "start_at")
    ea = _parse_iso(end_at, "end_at")
    if sa >= ea:
        raise ValueError("start_at must be earlier than end_at")
    return await db.insert_returning_id(
        "INSERT INTO staff_shifts(staff_id, start_at, end_at, created_at) "
        "VALUES (:sid, :sa, :ea, :now) RETURNING id",
        {"sid": staff_id, "sa": start_at, "ea": end_at, "now": now_str()},
    )


async def list_shifts(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, staff_id, start_at, end_at, created_at FROM staff_shifts "
        "WHERE (CAST(:sid AS TEXT) IS NULL OR staff_id = :sid) "
        "AND (CAST(:df AS TEXT) IS NULL OR start_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR end_at <= :dt) "
        "ORDER BY start_at LIMIT :lim",
        {"sid": staff_id, "df": date_from, "dt": date_to, "lim": limit},
    )


async def patch_shift(shift_id: int, fields: dict) -> dict | None:
    """Update provided fields; return updated row or None if not found."""
    allowed = {"staff_id", "start_at", "end_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError("no updatable fields")
    if "start_at" in updates:
        _parse_iso(updates["start_at"], "start_at")
    if "end_at" in updates:
        _parse_iso(updates["end_at"], "end_at")
    # 合并旧值校验 start < end（patch 可能只改一边）
    current = await db.fetch_one(
        "SELECT staff_id, start_at, end_at FROM staff_shifts WHERE id = :id",
        {"id": int(shift_id)},
    )
    if current is None:
        return None
    final_sa = updates.get("start_at", current["start_at"])
    final_ea = updates.get("end_at", current["end_at"])
    if _parse_iso(final_sa, "start_at") >= _parse_iso(final_ea, "end_at"):
        raise ValueError("start_at must be earlier than end_at")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = int(shift_id)
    await db.execute(
        f"UPDATE staff_shifts SET {set_clause} WHERE id = :id", updates
    )
    rows = await db.fetch_all(
        "SELECT id, staff_id, start_at, end_at, created_at FROM staff_shifts WHERE id = :id",
        {"id": int(shift_id)},
    )
    return rows[0] if rows else None


async def delete_shift(shift_id: int) -> int:
    """删除班次；返回受影响行数（0 表示 shift_id 不存在，端点用于 404 判定）。"""
    return await db.execute_rowcount(
        "DELETE FROM staff_shifts WHERE id = :id", {"id": int(shift_id)}
    )
