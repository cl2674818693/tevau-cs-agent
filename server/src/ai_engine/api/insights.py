"""知识缺口报表端点（staff 鉴权）。汇总"AI 差了什么"的可靠信号。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence.insights import (
    gap_conversations,
    knowledge_gaps,
    tool_health,
)

router = APIRouter()


@router.get("/staff/api/v1/insights/knowledge-gaps")
async def gaps(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """范围外 / 失败回合 / 差评 / 转人工 四项计数（可带 from/to 时间窗）。"""
    return {"from": date_from, "to": date_to, **(await knowledge_gaps(date_from, date_to))}


@router.get("/staff/api/v1/insights/tool-health")
async def tools(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """按工具的调用/空结果/拒绝聚合（含 empty_rate），可带 from/to 时间窗。"""
    return {
        "from": date_from,
        "to": date_to,
        "tools": await tool_health(date_from, date_to),
    }


@router.get("/staff/api/v1/insights/gap-conversations")
async def gap_convs(
    kind: str = Query(...),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """按信号下钻会话列表。kind ∈ {out_of_scope,failed,thumbs_down,human_handoff}。"""
    try:
        rows = await gap_conversations(kind, date_from, date_to, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"from": date_from, "to": date_to, "kind": kind, "conversations": rows}
