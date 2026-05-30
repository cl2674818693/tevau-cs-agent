"""核心指标大盘（supervisor/manager/admin）。复用 staff_metrics.ai_quality 聚合，
不重复造轮子；首页一次取齐转人工率/差评率/工具空结果率/超范围/失败回合。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence.staff_metrics import ai_quality

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


@router.get("/admin/api/v1/dashboard/overview")
async def overview(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    return await ai_quality(date_from, date_to)
