"""排班 CRUD + 按客服/时间范围查询。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_shift(staff_id: str, start_at: str, end_at: str) -> int:
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


async def delete_shift(shift_id: int) -> None:
    await db.execute("DELETE FROM staff_shifts WHERE id = :id", {"id": int(shift_id)})
