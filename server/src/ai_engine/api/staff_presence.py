"""客服在线状态：自心跳（任何 staff）+ 后台查询（supervisor/admin）。"""

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles, require_staff
from ai_engine.persistence import staff_presence

logger = logging.getLogger(__name__)
router = APIRouter()
_sup = require_roles("supervisor", "admin")

_VALID_STATUS = {"online", "offline"}


class HeartbeatIn(BaseModel):
    status: str = "online"


@router.post("/staff/api/v1/presence")
async def heartbeat(
    body: HeartbeatIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    # 非白名单 status 静默回退 online 保持兼容；加 debug 日志便于排查"前端发了什么"。
    if body.status not in _VALID_STATUS:
        logger.debug("invalid presence status %r, defaulting to online", body.status)
        status = "online"
    else:
        status = body.status
    staff_id = str(staff.get("sub", ""))
    if not staff_id:
        return {"ok": False}
    await staff_presence.heartbeat(staff_id, status)
    released_count = 0
    if status == "offline":
        from ai_engine.api.staff_conversations import publish_conversation_event
        released_ids = await staff_presence.release_pending_assignments(staff_id)
        for cid in released_ids:
            publish_conversation_event(cid, {"type": "conversation_assignment_cleared"})
        released_count = len(released_ids)
    return {"ok": True, "released_count": released_count}


@router.get("/admin/api/v1/presence")
async def admin_list(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    all_rows = await staff_presence.list_all()
    # M4: 窗口与前端心跳间隔同步加大（5min 心跳 → 容许 10min 内未掉线）
    active = await staff_presence.list_active(window_seconds=600)
    return {"all": all_rows, "active": active}
