"""客服绩效（supervisor/admin）：团队列表 + 单人详情。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence.staff_metrics import compute_kpi
from ai_engine.persistence.staff_performance import compute_performance

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/staff/performance")
async def list_performance(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    """团队绩效列表：所有客服的 KPI 汇总 + 团队聚合均值。"""
    rows = await compute_kpi(date_from, date_to)
    total = len(rows)
    team_takeovers = sum(r["takeovers"] for r in rows)
    team_resolved = sum(r["resolved"] for r in rows)
    team_transfers = sum(r["transfers"] for r in rows)
    team_avg_handle = (
        round(sum(r["avg_handle_seconds"] for r in rows) / total, 1) if total else 0.0
    )
    return {
        "from": date_from,
        "to": date_to,
        "team": {
            "staff_count": total,
            "total_takeovers": team_takeovers,
            "total_resolved": team_resolved,
            "total_transfers": team_transfers,
            "avg_handle_seconds": team_avg_handle,
        },
        "staff": rows,
    }


@router.get("/admin/api/v1/staff/{staff_id}/performance")
async def get_performance(
    staff_id: str,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return await compute_performance(staff_id, date_from, date_to)
