"""客服/管理后台 留痕查看（只读，staff 鉴权）。

把已落库但此前无读取接口的明细暴露给管理后台：
- 会话完整消息历史（含 status / topic_verdict / error_code）
- 会话工具调用审计
- 会话反馈（👍/👎）
- 跨会话近期工具审计流（可只看被拒）
聚合口径的知识缺口报表在 insights.py。
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import audit as audit_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import feedback as fb_dao

router = APIRouter()


@router.get("/staff/api/v1/conversations/{conv_id}/messages")
async def conversation_messages(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """会话完整消息历史（含 status/topic_verdict/error_code），用于留痕回看。"""
    return {"conversation_id": conv_id, "messages": await conv_dao.list_messages(conv_id)}


@router.get("/staff/api/v1/conversations/{conv_id}/tool-audits")
async def conversation_tool_audits(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """会话内全部工具调用审计（参数/是否被拒/拒绝原因/耗时）。"""
    return {"conversation_id": conv_id, "audits": await audit_dao.list_audits(conv_id)}


@router.get("/staff/api/v1/conversations/{conv_id}/feedback")
async def conversation_feedback(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """会话内全部 👍/👎 反馈。"""
    return {"conversation_id": conv_id, "feedback": await fb_dao.list_feedback(conv_id)}


@router.get("/staff/api/v1/audits/recent")
async def recent_tool_audits(
    rejected: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
    tool_name: str | None = Query(default=None),
    empty_only: bool = Query(default=False),
    conversation_id: int | None = Query(default=None),
    before_id: int | None = Query(default=None),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """跨会话近期工具调用审计流（最新在前）。

    可选筛选：rejected / tool_name / empty_only / conversation_id；游标分页：before_id。
    """
    return {
        "audits": await audit_dao.recent_audits(
            limit=limit,
            rejected_only=rejected,
            tool_name=tool_name,
            empty_only=empty_only,
            conversation_id=conversation_id,
            before_id=before_id,
        )
    }
