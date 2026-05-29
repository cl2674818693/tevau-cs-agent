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
from ai_engine.persistence import attachments as att_dao
from ai_engine.persistence import audit as audit_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import feedback as fb_dao

router = APIRouter()


@router.get("/staff/api/v1/conversations/{conv_id}/messages")
async def conversation_messages(
    conv_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """会话消息历史（含 status/topic_verdict/error_code + 图片附件），用于留痕回看。

    分页：默认取最新 limit 条（升序返回）；往上"加载更早"传 before_id=当前最旧消息 id。
    has_more 用满页启发式（与列表页一致），为 true 时仍可能有更早消息。
    """
    messages = await conv_dao.list_messages_page(conv_id, limit, before_id)
    has_more = len(messages) >= limit
    att_map = await att_dao.list_for_conversation(conv_id)  # message_id -> [{id, mime}]
    for m in messages:
        # assistant 入库是 content-block JSON，留痕展示需还原纯文本（与用户侧历史一致）
        m["content"] = conv_dao.message_content_text(str(m["role"]), str(m["content"]))
        m["attachments"] = att_map.get(int(m["id"]), [])
    return {"conversation_id": conv_id, "messages": messages, "has_more": has_more}


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
    page: int = Query(default=1, ge=1),
    before_id: int | None = Query(default=None),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """跨会话近期工具调用审计流（最新在前）。

    可选筛选：rejected / tool_name / empty_only / conversation_id。
    分页：页码式（page，1 基；返回 total/page/limit 供页码导航）。
    before_id 游标分页保留兼容；传 before_id 时忽略 page。
    """
    offset = 0 if before_id is not None else (page - 1) * limit
    audits = await audit_dao.recent_audits(
        limit=limit,
        rejected_only=rejected,
        tool_name=tool_name,
        empty_only=empty_only,
        conversation_id=conversation_id,
        before_id=before_id,
        offset=offset,
    )
    total = await audit_dao.count_recent_audits(
        rejected_only=rejected,
        tool_name=tool_name,
        empty_only=empty_only,
        conversation_id=conversation_id,
    )
    return {"audits": audits, "total": total, "page": page, "limit": limit}
