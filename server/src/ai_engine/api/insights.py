"""知识缺口报表端点（staff 鉴权）。汇总"AI 差了什么"的可靠信号。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence.insights import knowledge_gaps

router = APIRouter()


@router.get("/staff/api/v1/insights/knowledge-gaps")
async def gaps(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """范围外 / 失败回合 / 差评 三项计数（可带 from/to 时间窗）。"""
    return {"from": date_from, "to": date_to, **(await knowledge_gaps(date_from, date_to))}
