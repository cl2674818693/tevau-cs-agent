"""排班管理（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_shifts

router = APIRouter()
_sup = require_roles("supervisor", "admin")


def _normalize_dt_bound(s: str | None, end_of_day: bool) -> str | None:
    # YYYY-MM-DD 自动补全为同日 00:00:00 / 23:59:59，便于前端日期选择器直接过滤。
    if s is None or len(s) != 10 or "T" in s:
        return s
    return s + ("T23:59:59" if end_of_day else "T00:00:00")


@router.get("/admin/api/v1/shifts")
async def list_shifts(
    staff_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {
        "shifts": await admin_shifts.list_shifts(
            staff_id=staff_id,
            date_from=_normalize_dt_bound(date_from, end_of_day=False),
            date_to=_normalize_dt_bound(date_to, end_of_day=True),
            limit=limit,
        )
    }


class ShiftIn(BaseModel):
    staff_id: str
    start_at: str
    end_at: str


@router.post("/admin/api/v1/shifts")
async def create_shift(body: ShiftIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    try:
        sid = await admin_shifts.create_shift(body.staff_id, body.start_at, body.end_at)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": sid}


class PatchShiftBody(BaseModel):
    staff_id: str | None = None
    start_at: str | None = None
    end_at: str | None = None


@router.patch("/admin/api/v1/shifts/{shift_id}")
async def patch_shift(
    shift_id: int,
    body: PatchShiftBody,
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        row = await admin_shifts.patch_shift(shift_id, update_fields)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if row is None:
        raise HTTPException(404, "shift not found")
    return row


@router.delete("/admin/api/v1/shifts/{shift_id}")
async def delete_shift(shift_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    # DELETE 0 行 → 404，避免对不存在 ID 的删除请求静默成功。
    if await admin_shifts.delete_shift(shift_id) == 0:
        raise HTTPException(404, "shift not found")
    return {"ok": True}
