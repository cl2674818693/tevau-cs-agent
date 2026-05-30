"""动态 RBAC（admin only）。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, rbac

router = APIRouter()
_admin = require_roles("admin")


@router.get("/admin/api/v1/rbac/matrix")
async def get_matrix(staff: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    return {
        "matrix": await rbac.list_matrix(),
        "roles": rbac.ROLES,
        "permission_keys": rbac.PERMISSION_KEYS,
    }


class PermItem(BaseModel):
    role: str
    permission_key: str
    allowed: int


class UpsertIn(BaseModel):
    items: list[PermItem]


@router.put("/admin/api/v1/rbac/matrix")
async def upsert(body: UpsertIn, staff: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    n = await rbac.upsert_many(actor=actor, items=[it.model_dump() for it in body.items])
    await admin_audit.log_admin_action(
        actor=actor, action="rbac.upsert",
        target_type="role_permissions", target_id=None,
        detail={"count": n},
    )
    return {"ok": True, "count": n}
