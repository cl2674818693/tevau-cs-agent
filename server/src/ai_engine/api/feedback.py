"""消息级反馈端点（spec 留痕）。用户对某条 AI 回复点 👍/👎，落库 + 计数。"""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.api.chat import _authorize_conversation
from ai_engine.observability import metrics
from ai_engine.persistence import feedback as fb_dao

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
    return {"ok": True}
