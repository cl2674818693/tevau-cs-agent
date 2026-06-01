"""客服分组管理（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_staff_groups

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/staff-groups")
async def list_groups(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"groups": await admin_staff_groups.list_groups()}


class GroupIn(BaseModel):
    name: str
    description: str | None = None


@router.post("/admin/api/v1/staff-groups")
async def create_group(body: GroupIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    gid = await admin_staff_groups.create_group(body.name, body.description)
    return {"ok": True, "id": gid}


class GroupPatchIn(BaseModel):
    name: str | None = None
    description: str | None = None
    active: int | None = None


@router.patch("/admin/api/v1/staff-groups/{group_id}")
async def patch_group(
    group_id: int, body: GroupPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    if body.name is not None or body.description is not None:
        await admin_staff_groups.update_group(group_id, body.name, body.description)
    if body.active is not None:
        await admin_staff_groups.set_group_active(group_id, body.active)
    return {"ok": True}


@router.delete("/admin/api/v1/staff-groups/{group_id}")
async def delete_group(
    group_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await admin_staff_groups.delete_group(group_id)
    return {"ok": True}
