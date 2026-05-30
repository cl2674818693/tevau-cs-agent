"""客服在线状态：自心跳（任何 staff）+ 后台查询（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles, require_staff
from ai_engine.persistence import staff_presence

router = APIRouter()
_sup = require_roles("supervisor", "admin")

_VALID_STATUS = {"online", "away", "offline"}


class HeartbeatIn(BaseModel):
    status: str = "online"


@router.post("/staff/api/v1/presence")
async def heartbeat(
    body: HeartbeatIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    status = body.status if body.status in _VALID_STATUS else "online"
    staff_id = str(staff.get("sub", ""))
    if not staff_id:
        return {"ok": False}
    await staff_presence.heartbeat(staff_id, status)
    return {"ok": True}


@router.get("/admin/api/v1/presence")
async def admin_list(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    all_rows = await staff_presence.list_all()
    active = await staff_presence.list_active(window_seconds=300)
    return {"all": all_rows, "active": active}
