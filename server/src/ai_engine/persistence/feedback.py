"""消息级 👍/👎 反馈落库。采集"答了但不满意"的细粒度信号，供知识缺口统计。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def add_feedback(
    conversation_id: int,
    message_id: int,
    rating: str,
    reason: str | None,
    subject_id: str,
    user_type: str,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO message_feedback"
        "(conversation_id, message_id, rating, reason, subject_id, user_type, created_at) "
        "VALUES (:cid, :mid, :r, :reason, :sid, :ut, :now) RETURNING id",
        {
            "cid": conversation_id,
            "mid": message_id,
            "r": rating,
            "reason": reason,
            "sid": subject_id,
            "ut": user_type,
            "now": now_str(),
        },
    )


async def list_feedback(conversation_id: int) -> list[dict[str, Any]]:
    """某会话的全部反馈（按时间）。供客服留痕查看。"""
    return await db.fetch_all(
        "SELECT id, message_id, rating, reason, created_at FROM message_feedback "
        "WHERE conversation_id=:cid ORDER BY id",
        {"cid": conversation_id},
    )
