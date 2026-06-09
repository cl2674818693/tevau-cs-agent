"""用户对人工客服的满意度评分（1-5 星，会话维度，subject 强隔离）。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def record(
    conversation_id: int,
    staff_id: str,
    subject_id: str,
    user_type: str,
    rating: int,
    comment: str | None,
) -> int:
    if rating < 1 or rating > 5:
        raise ValueError("rating must be 1..5")
    return await db.insert_returning_id(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, comment, created_at) "
        "VALUES (:cid, :sid, :subj, :ut, :rating, :cmt, :now)",
        {
            "cid": int(conversation_id),
            "sid": staff_id,
            "subj": subject_id,
            "ut": user_type,
            "rating": int(rating),
            "cmt": comment,
            "now": now_str(),
        },
    )


async def get_for_conversation(
    conversation_id: int, subject_id: str
) -> dict[str, Any] | None:
    """同会话同 subject 的评分（用于查询是否已评过）。"""
    return await db.fetch_one(
        "SELECT id, rating, comment, created_at FROM agent_ratings "
        "WHERE conversation_id = :cid AND subject_id = :subj "
        "ORDER BY id DESC LIMIT 1",
        {"cid": int(conversation_id), "subj": subject_id},
    )


async def aggregate_by_staff(
    staff_id: str, date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    row = await db.fetch_one(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg_rating FROM agent_ratings "
        "WHERE staff_id = :sid "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt)",
        {"sid": staff_id, "df": date_from, "dt": date_to},
    )
    return {
        "count": int(row["n"]) if row and row["n"] is not None else 0,
        "avg_rating": float(row["avg_rating"]) if row and row["avg_rating"] is not None else 0.0,
    }


async def list_for_admin(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, conversation_id, staff_id, user_type, rating, comment, created_at "
        "FROM agent_ratings "
        "WHERE (CAST(:sid AS TEXT) IS NULL OR staff_id = :sid) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {"sid": staff_id, "df": date_from, "dt": date_to, "lim": limit, "off": offset},
    )
