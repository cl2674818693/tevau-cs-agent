from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence.tickets import (
    get_ticket,
    list_tickets,
)

# 旧的 HMAC 入站端点 POST /api/v1/tickets/{external_id}/events 已废弃：
# 事项中心契约改用 Bearer + 单一回调端点 POST /api/v1/event-center/callback
# （见 api/event_center_callback.py）。原 _verify + receive_event + _observe_resolution
# 一并移除——解决耗时 metric 现在由 event_center_callback 调用方维护。

router = APIRouter()


@router.get("/staff/api/v1/tickets")
async def staff_list_tickets(
    open: bool = Query(default=False),
    severity: str | None = Query(default=None),
    category: str | None = Query(default=None),
    before_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """运营只读工单列表（看 + 跳会话）。外部事项中心是状态真源，本地仅只读镜像。

    可选筛选：open（只看未关闭）/ severity / category；游标分页：before_id。
    """
    return {
        "tickets": await list_tickets(
            open_only=open,
            severity=severity,
            category=category,
            limit=limit,
            before_id=before_id,
        )
    }


@router.get("/staff/api/v1/tickets/{external_id}")
async def staff_get_ticket(
    external_id: str, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """工单详情（含事件链）。本地只读镜像，外部事项中心为状态真源。"""
    t = await get_ticket(external_id)
    if t is None:
        raise HTTPException(404, "ticket not found")
    return t


