"""客服分组 CRUD。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_group(name: str, description: str | None) -> int:
    return await db.insert_returning_id(
        "INSERT INTO staff_groups(name, description, created_at) "
        "VALUES (:n, :d, :now) RETURNING id",
        {"n": name, "d": description, "now": now_str()},
    )


async def list_groups(active_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, name, description, active, created_at FROM staff_groups"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    return await db.fetch_all(sql)


async def update_group(
    group_id: int, name: str | None = None, description: str | None = None
) -> None:
    await db.execute(
        "UPDATE staff_groups SET "
        "name = COALESCE(CAST(:n AS TEXT), name), "
        "description = COALESCE(CAST(:d AS TEXT), description) "
        "WHERE id = :id",
        {"n": name, "d": description, "id": int(group_id)},
    )


async def set_group_active(group_id: int, active: int) -> None:
    await db.execute(
        "UPDATE staff_groups SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(group_id)},
    )


async def delete_group(group_id: int) -> None:
    await db.execute("DELETE FROM staff_groups WHERE id = :id", {"id": int(group_id)})
