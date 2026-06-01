"""客服账号管理（admin only）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import staff as staff_mod

router = APIRouter()
_admin = require_roles("admin")


@router.get("/admin/api/v1/staff")
async def list_staff(admin: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    return {"staff": await staff_mod.list_staff()}


class StaffCreateIn(BaseModel):
    staff_id: str
    display_name: str
    role: str
    password: str


@router.post("/admin/api/v1/staff")
async def create_staff(
    body: StaffCreateIn, admin: dict[str, Any] = Depends(_admin)
) -> dict[str, Any]:
    try:
        new_id = await staff_mod.create_staff(
            body.staff_id, body.display_name, body.role, body.password
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": new_id}


class StaffPatchIn(BaseModel):
    display_name: str | None = None
    role: str | None = None
    active: int | None = None
    group_id: int | None = None
    skills: list[str] | None = None


@router.patch("/admin/api/v1/staff/{staff_id}")
async def patch_staff(
    staff_id: str, body: StaffPatchIn, admin: dict[str, Any] = Depends(_admin)
) -> dict[str, Any]:
    try:
        if body.display_name is not None or body.role is not None:
            await staff_mod.update_staff(staff_id, display_name=body.display_name, role=body.role)
        if body.active is not None:
            await staff_mod.set_staff_active(staff_id, body.active)
        if "group_id" in body.model_fields_set:
            await staff_mod.set_staff_group(staff_id, body.group_id)
        if body.skills is not None:
            await staff_mod.set_staff_skills(staff_id, body.skills)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


class ResetPwIn(BaseModel):
    password: str


@router.post("/admin/api/v1/staff/{staff_id}/reset-password")
async def reset_password(
    staff_id: str, body: ResetPwIn, admin: dict[str, Any] = Depends(_admin)
) -> dict[str, Any]:
    await staff_mod.reset_staff_password(staff_id, body.password)
    return {"ok": True}
