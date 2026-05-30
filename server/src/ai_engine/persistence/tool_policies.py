"""AI 工具按角色的策略：先查 DB；缺行回退到代码默认。

代码默认（_STAFF_DEFAULT_TOOLS）必须与既有 _STAFF_TOOL_WHITELIST 和 dispatch 的 unmask 规则一致，
保证 M2 上线时即便表空、行为也与 M1 一致；后台后续可在 DB 里改。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

# 与 api/staff_conversations.py 的 _STAFF_TOOL_WHITELIST 一致（默认放行的工具集合）
_STAFF_DEFAULT_TOOLS: set[str] = {
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


def _default_allowed(tool_name: str, role: str) -> bool:
    # M1 既有逻辑：客服(含 senior/engineer/admin)都能代查白名单内工具；
    # supervisor/manager 不参与代查，默认拒。
    if role in {"agent", "senior", "engineer", "admin"}:
        return tool_name in _STAFF_DEFAULT_TOOLS
    return False


def _default_unmask(tool_name: str, role: str) -> bool:
    # M1 既有逻辑：仅 engineer 可解锁脱敏
    return role == "engineer"


# 模块级缓存：键 = (tool_name, role)，值 = (allowed:int, unmask:int) 或 None（未命中 DB）
_CACHE: dict[tuple[str, str], tuple[int, int] | None] = {}


def invalidate_cache() -> None:
    _CACHE.clear()


async def _load_row(tool_name: str, role: str) -> tuple[int, int] | None:
    key = (tool_name, role)
    if key in _CACHE:
        return _CACHE[key]
    row = await db.fetch_one(
        "SELECT allowed, unmask_allowed FROM tool_policies "
        "WHERE tool_name = :t AND role = :r",
        {"t": tool_name, "r": role},
    )
    val = (int(row["allowed"]), int(row["unmask_allowed"])) if row else None
    _CACHE[key] = val
    return val


async def is_tool_allowed(tool_name: str, role: str) -> bool:
    row = await _load_row(tool_name, role)
    if row is None:
        return _default_allowed(tool_name, role)
    return row[0] == 1


async def is_unmask_allowed(tool_name: str, role: str) -> bool:
    row = await _load_row(tool_name, role)
    if row is None:
        return _default_unmask(tool_name, role)
    return row[1] == 1


async def list_all() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT tool_name, role, allowed, unmask_allowed, updated_by, updated_at "
        "FROM tool_policies ORDER BY tool_name, role"
    )


async def upsert_many(actor: str, items: list[dict[str, Any]]) -> int:
    """批量 upsert (tool_name, role, allowed, unmask_allowed)。返回更新条数。

    两库 portable 实现：逐行 SELECT 1 → UPDATE / INSERT。M2 规模可接受。
    """
    n = 0
    now = now_str()
    for it in items:
        tool = str(it["tool_name"])
        role = str(it["role"])
        allowed = int(it.get("allowed", 0))
        unmask = int(it.get("unmask_allowed", 0))
        existing = await db.fetch_one(
            "SELECT id FROM tool_policies WHERE tool_name = :t AND role = :r",
            {"t": tool, "r": role},
        )
        if existing is None:
            await db.execute(
                "INSERT INTO tool_policies(tool_name, role, allowed, unmask_allowed, "
                "updated_by, updated_at) VALUES (:t, :r, :a, :u, :by, :now)",
                {"t": tool, "r": role, "a": allowed, "u": unmask, "by": actor, "now": now},
            )
        else:
            await db.execute(
                "UPDATE tool_policies SET allowed = :a, unmask_allowed = :u, "
                "updated_by = :by, updated_at = :now WHERE id = :id",
                {"a": allowed, "u": unmask, "by": actor, "now": now, "id": existing["id"]},
            )
        n += 1
    invalidate_cache()
    return n
