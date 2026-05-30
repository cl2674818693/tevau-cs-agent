"""范围 / 拦截规则 persistence + evaluate helper。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_TYPES = {"blocklist", "sensitive_word", "scope_toggle"}
_VALID_ACTIONS = {"block", "flag"}

_CACHE: list[dict[str, Any]] | None = None


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _active_rules() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT id, type, pattern, action FROM guardrail_rules "
        "WHERE active = 1 ORDER BY id"
    )
    _CACHE = rows
    return rows


async def create_rule(type_: str, pattern: str, action: str, created_by: str) -> int:
    if type_ not in _VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if action not in _VALID_ACTIONS:
        raise ValueError(f"invalid action: {action}")
    rid = await db.insert_returning_id(
        "INSERT INTO guardrail_rules(type, pattern, action, created_by, created_at) "
        "VALUES (:t, :p, :a, :by, :now) RETURNING id",
        {"t": type_, "p": pattern, "a": action, "by": created_by, "now": now_str()},
    )
    invalidate_cache()
    return rid


async def list_rules() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, type, pattern, action, active, created_by, created_at "
        "FROM guardrail_rules ORDER BY id"
    )


async def set_active(rule_id: int, active: int) -> None:
    await db.execute(
        "UPDATE guardrail_rules SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(rule_id)},
    )
    invalidate_cache()


async def delete_rule(rule_id: int) -> None:
    await db.execute(
        "DELETE FROM guardrail_rules WHERE id = :id", {"id": int(rule_id)}
    )
    invalidate_cache()


async def evaluate(
    subject_id: str, user_type: str, text: str, scope: str | None = None
) -> tuple[str, str | None]:
    """返回 ("allow", None) 或 ("block"|"flag", reason)。

    M4: scope_toggle 规则——pattern 是 scope 名（如 "stock"），调用方传 scope 命中即触发。
    """
    for rule in await _active_rules():
        t = str(rule["type"])
        pat = str(rule["pattern"])
        action = str(rule["action"])
        if t == "blocklist" and pat == subject_id:
            return action, f"blocklist:{pat}"
        if t == "sensitive_word" and pat in text:
            return action, f"sensitive_word:{pat}"
        if t == "scope_toggle" and scope is not None and pat == scope:
            return action, f"scope_toggle:{pat}"
    return "allow", None
