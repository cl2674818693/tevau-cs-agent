from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence.staff_metrics import compute_kpi

router = APIRouter()


@router.get("/staff/api/v1/kpi")
async def kpi(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """客服 KPI 看板：接管数 / 平均接管时长 / 释放回 AI 比例 / 解决率。"""
    rows = await compute_kpi(date_from, date_to)
    return {"from": date_from, "to": date_to, "staff": rows}
