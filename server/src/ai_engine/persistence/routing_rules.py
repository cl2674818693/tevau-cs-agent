"""会话路由规则 CRUD + 路由匹配。

匹配方式简化：active 规则按 priority 升序遍历，第一条命中返回 target_group_id。
- user_type: 匹配 user_type == match_value
- scope/keyword: substring 匹配 last_user_text

模块级缓存：upsert/delete/set_active 后调 invalidate_cache。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_MATCH = {"user_type", "scope", "keyword"}
_CACHE: list[dict[str, Any]] | None = None


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _active_rules_sorted() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT id, match_type, match_value, target_group_id, priority, active "
        "FROM routing_rules WHERE active = 1 ORDER BY priority ASC, id ASC"
    )
    _CACHE = rows
    return rows


async def create_rule(
    match_type: str, match_value: str, target_group_id: int, priority: int = 100
) -> int:
    if match_type not in _VALID_MATCH:
        raise ValueError(f"invalid match_type: {match_type}")
    rid = await db.insert_returning_id(
        "INSERT INTO routing_rules(match_type, match_value, target_group_id, priority, "
        "created_at) VALUES (:mt, :mv, :tg, :pr, :now) RETURNING id",
        {
            "mt": match_type,
            "mv": match_value,
            "tg": int(target_group_id),
            "pr": int(priority),
            "now": now_str(),
        },
    )
    invalidate_cache()
    return rid


async def list_rules() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, match_type, match_value, target_group_id, priority, active, created_at "
        "FROM routing_rules ORDER BY priority ASC, id ASC"
    )


async def patch_rule(rule_id: int, fields: dict) -> dict | None:
    """Update editable fields (not active); return updated row or None."""
    allowed = {"priority", "match_type", "match_value", "target_group_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError("no updatable fields")
    if "match_type" in updates and updates["match_type"] not in _VALID_MATCH:
        raise ValueError(f"invalid match_type: {updates['match_type']}")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["id"] = int(rule_id)
    await db.execute(
        f"UPDATE routing_rules SET {set_clause} WHERE id = :id", updates
    )
    invalidate_cache()
    rows = await db.fetch_all(
        "SELECT id, match_type, match_value, target_group_id, priority, active, created_at "
        "FROM routing_rules WHERE id = :id",
        {"id": int(rule_id)},
    )
    return rows[0] if rows else None


async def set_active(rule_id: int, active: int) -> None:
    await db.execute(
        "UPDATE routing_rules SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(rule_id)},
    )
    invalidate_cache()


async def delete_rule(rule_id: int) -> None:
    await db.execute("DELETE FROM routing_rules WHERE id = :id", {"id": int(rule_id)})
    invalidate_cache()


async def match_for_conversation(
    user_type: str, last_user_text: str | None
) -> int | None:
    """返回首个命中规则的 target_group_id；无命中返回 None。"""
    for rule in await _active_rules_sorted():
        mt = str(rule["match_type"])
        mv = str(rule["match_value"])
        if mt == "user_type" and user_type == mv:
            return int(rule["target_group_id"])
        if mt in ("scope", "keyword") and last_user_text and mv in last_user_text:
            return int(rule["target_group_id"])
    return None


async def route_conversation_now(conv_id: int, user_type: str) -> int | None:
    """读会话最近 user 消息文本 → 匹配规则 → 写 target_group_id。返回匹配到的 group_id 或 None。"""
    from ai_engine.persistence import conversations as conv_dao

    text = await conv_dao.last_user_text(conv_id)
    gid = await match_for_conversation(user_type=user_type, last_user_text=text)
    await conv_dao.set_target_group(conv_id, gid)
    return gid
