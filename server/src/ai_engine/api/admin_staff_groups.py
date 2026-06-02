"""客服分组管理（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

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
    try:
        gid = await admin_staff_groups.create_group(body.name, body.description)
    except IntegrityError as e:
        # ux_staff_group_name UNIQUE 重名：转 409 而不是 500（避免裸 IntegrityError 透传）。
        raise HTTPException(409, "group name already exists") from e
    return {"ok": True, "id": gid}


class GroupPatchIn(BaseModel):
    name: str | None = None
    description: str | None = None
    active: int | None = None


@router.patch("/admin/api/v1/staff-groups/{group_id}")
async def patch_group(
    group_id: int, body: GroupPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    # 至少一项被指定时用 rowcount 判存在性；空 body 走显式存在性查询（保持空 body=200 noop 但 ID 不存在仍 404）。
    touched = False
    if body.name is not None or body.description is not None:
        if await admin_staff_groups.update_group(group_id, body.name, body.description) == 0:
            raise HTTPException(404, "group not found")
        touched = True
    if body.active is not None:
        if await admin_staff_groups.set_group_active(group_id, body.active) == 0:
            raise HTTPException(404, "group not found")
        touched = True
    if not touched:
        # 空 body：显式存在性检查，避免静默 200。
        rows = await admin_staff_groups.list_groups()
        if not any(int(r["id"]) == int(group_id) for r in rows):
            raise HTTPException(404, "group not found")
    return {"ok": True}


@router.delete("/admin/api/v1/staff-groups/{group_id}")
async def delete_group(
    group_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    # DAO 内已先级联清空 staff.group_id；返回 0 说明组不存在。
    if await admin_staff_groups.delete_group(group_id) == 0:
        raise HTTPException(404, "group not found")
    return {"ok": True}
