"""动态 RBAC：role_permissions DB-first，缺行回退到 _DEFAULT_MATRIX。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

ROLES: list[str] = ["agent", "senior", "supervisor", "engineer", "manager", "admin"]

PERMISSION_KEYS: list[str] = [
    "admin.dashboard",
    "admin.staff",
    "admin.performance",
    "admin.qa",
    "admin.sla",
    "admin.tools",
    "admin.cost",
    "admin.audit",
    "admin.prompts",
    "admin.rbac",
    "admin.staff_groups",
    "admin.presence",
    "admin.shifts",
    "admin.routing",
    "admin.prompt_editor",
    "admin.knowledge",
    "admin.guardrails",
    "admin.reports",
]

_DEFAULT_MATRIX: dict[str, set[str]] = {
    "agent": set(),
    "senior": set(),
    "supervisor": {
        "admin.dashboard", "admin.performance", "admin.qa", "admin.sla",
        "admin.staff_groups", "admin.presence", "admin.shifts", "admin.routing",
        "admin.knowledge", "admin.reports",
    },
    "engineer": {
        "admin.tools", "admin.audit", "admin.cost",
        "admin.prompt_editor", "admin.knowledge", "admin.guardrails",
    },
    "manager": {"admin.dashboard", "admin.cost", "admin.reports"},
    "admin": set(PERMISSION_KEYS),
}


def _default_allowed(role: str, perm_key: str) -> bool:
    return perm_key in _DEFAULT_MATRIX.get(role, set())


_CACHE: dict[tuple[str, str], int] | None = None


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _load_cache() -> dict[tuple[str, str], int]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT role, permission_key, allowed FROM role_permissions"
    )
    _CACHE = {
        (str(r["role"]), str(r["permission_key"])): int(r["allowed"]) for r in rows
    }
    return _CACHE


async def is_permitted(role: str, perm_key: str) -> bool:
    cache = await _load_cache()
    key = (role, perm_key)
    if key in cache:
        return cache[key] == 1
    return _default_allowed(role, perm_key)


async def list_matrix() -> dict[str, dict[str, bool]]:
    cache = await _load_cache()
    out: dict[str, dict[str, bool]] = {}
    for role in ROLES:
        out[role] = {}
        for k in PERMISSION_KEYS:
            db_val = cache.get((role, k))
            out[role][k] = (db_val == 1) if db_val is not None else _default_allowed(role, k)
    return out


async def upsert_many(actor: str, items: list[dict[str, Any]]) -> int:
    n = 0
    now = now_str()
    for it in items:
        role = str(it["role"])
        perm = str(it["permission_key"])
        allowed = int(it.get("allowed", 0))
        existing = await db.fetch_one(
            "SELECT id FROM role_permissions WHERE role = :r AND permission_key = :p",
            {"r": role, "p": perm},
        )
        if existing is None:
            await db.execute(
                "INSERT INTO role_permissions(role, permission_key, allowed, "
                "updated_by, updated_at) VALUES (:r, :p, :a, :by, :now)",
                {"r": role, "p": perm, "a": allowed, "by": actor, "now": now},
            )
        else:
            await db.execute(
                "UPDATE role_permissions SET allowed = :a, updated_by = :by, "
                "updated_at = :now WHERE id = :id",
                {"a": allowed, "by": actor, "now": now, "id": existing["id"]},
            )
        n += 1
    invalidate_cache()
    return n
