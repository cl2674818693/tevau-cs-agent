"""单客服绩效详情（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence.staff_performance import compute_performance

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/staff/{staff_id}/performance")
async def get_performance(
    staff_id: str,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return await compute_performance(staff_id, date_from, date_to)
