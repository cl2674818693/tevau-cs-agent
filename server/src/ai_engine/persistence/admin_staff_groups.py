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
) -> int:
    """部分更新组名/描述；返回受影响行数（0 表示 group_id 不存在）。"""
    return await db.execute_rowcount(
        "UPDATE staff_groups SET "
        "name = COALESCE(CAST(:n AS TEXT), name), "
        "description = COALESCE(CAST(:d AS TEXT), description) "
        "WHERE id = :id",
        {"n": name, "d": description, "id": int(group_id)},
    )


async def set_group_active(group_id: int, active: int) -> int:
    """切换启用；返回受影响行数（0 表示 group_id 不存在）。"""
    return await db.execute_rowcount(
        "UPDATE staff_groups SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(group_id)},
    )


async def delete_group(group_id: int) -> int:
    """删除分组：先级联清空 staff.group_id 引用（schema 无 FK，否则成为孤儿引用），再 DELETE。
    返回 DELETE 受影响行数（0 表示 group_id 不存在，端点用于 404 判定）。
    """
    # 顺序：先解绑 staff，再删组；同事务内即使 DELETE 0 行也已经把孤儿引用清掉。
    from ai_engine.persistence import staff as staff_mod

    await staff_mod.clear_staff_group_refs(group_id)
    return await db.execute_rowcount(
        "DELETE FROM staff_groups WHERE id = :id", {"id": int(group_id)}
    )
