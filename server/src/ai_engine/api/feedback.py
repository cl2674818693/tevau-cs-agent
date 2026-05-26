"""消息级反馈端点（spec 留痕）。用户对某条 AI 回复点 👍/👎，落库 + 计数。

👎 不再是黑洞：触发 Lark 告警 + 标记会话 needs_review，供运营筛出复核。
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.api.chat import _authorize_conversation
from ai_engine.integrations.lark_webhook import send as _notify_lark
from ai_engine.observability import metrics
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import feedback as fb_dao

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedbackIn(BaseModel):
    message_id: int
    rating: str  # "up" | "down"
    reason: str | None = None


@router.post("/api/v1/conversations/{conv_id}/feedback")
async def submit_feedback(conv_id: int, body: FeedbackIn, request: Request) -> dict[str, Any]:
    if body.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be up/down")
    # 复用 chat 的归属校验，防 IDOR 横向越权
    user_type, subject_id = await _authorize_conversation(request, conv_id)
    await fb_dao.add_feedback(
        conv_id, body.message_id, body.rating, body.reason, subject_id, user_type
    )
    metrics.message_feedback_total.labels(rating=body.rating).inc()

    if body.rating == "down":
        # 标记待复核（落库成功是主流程，必须执行）
        await conv_dao.mark_needs_review(conv_id)
        # Lark 告警是尽力而为：失败只 log，不阻断反馈本身
        reason_part = f"，原因：{body.reason}" if body.reason else ""
        text = (
            f"[差评] 会话 {conv_id} 消息 {body.message_id} 被点👎"
            f"{reason_part}（{user_type} 用户 {subject_id}）。请进工作台复核。"
        )
        try:
            await _notify_lark({"text": text})
        except Exception:
            logger.exception("差评 Lark 告警发送失败 conv=%s msg=%s", conv_id, body.message_id)

    return {"ok": True}
