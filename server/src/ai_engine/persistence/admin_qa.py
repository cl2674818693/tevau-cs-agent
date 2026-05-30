"""会话质检：评分卡 CRUD + 质检提交/列表。"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_scorecard(name: str, items: list[dict[str, Any]]) -> int:
    return await db.insert_returning_id(
        "INSERT INTO qa_scorecards(name, items_json, created_at) "
        "VALUES (:n, :items, :now) RETURNING id",
        {"n": name, "items": json.dumps(items, ensure_ascii=False), "now": now_str()},
    )


async def list_scorecards(active_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, name, items_json, active, created_at FROM qa_scorecards"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    return await db.fetch_all(sql)


async def set_scorecard_active(scorecard_id: int, active: int) -> None:
    await db.execute(
        "UPDATE qa_scorecards SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(scorecard_id)},
    )


async def submit_review(
    conversation_id: int,
    reviewer_staff_id: str,
    scorecard_id: int,
    score: int,
    items_result: dict[str, Any],
    tags: str | None = None,
    comment: str | None = None,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO qa_reviews(conversation_id, reviewer_staff_id, scorecard_id, score, "
        "items_result_json, tags, comment, created_at) "
        "VALUES (:cid, :sid, :sc, :score, :items, :tags, :cmt, :now) RETURNING id",
        {
            "cid": int(conversation_id),
            "sid": reviewer_staff_id,
            "sc": int(scorecard_id),
            "score": int(score),
            "items": json.dumps(items_result, ensure_ascii=False),
            "tags": tags,
            "cmt": comment,
            "now": now_str(),
        },
    )


async def list_reviews(
    conversation_id: int | None = None,
    reviewer_staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, conversation_id, reviewer_staff_id, scorecard_id, score, "
        "items_result_json, tags, comment, created_at FROM qa_reviews "
        "WHERE (CAST(:cid AS TEXT) IS NULL OR conversation_id = :cid) "
        "AND (CAST(:rsid AS TEXT) IS NULL OR reviewer_staff_id = :rsid) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {
            "cid": conversation_id, "rsid": reviewer_staff_id,
            "df": date_from, "dt": date_to,
            "lim": limit, "off": offset,
        },
    )


async def avg_score_by_reviewer(
    reviewer_staff_id: str, date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    """绩效详情用：单客服质检均分 + 计数。"""
    row = await db.fetch_one(
        "SELECT COUNT(*) AS n, AVG(score) AS avg_score FROM qa_reviews "
        "WHERE reviewer_staff_id = :rsid "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt)",
        {"rsid": reviewer_staff_id, "df": date_from, "dt": date_to},
    )
    return {
        "count": int(row["n"]) if row and row["n"] is not None else 0,
        "avg_score": float(row["avg_score"]) if row and row["avg_score"] is not None else 0.0,
    }
