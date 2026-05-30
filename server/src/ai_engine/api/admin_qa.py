"""会话质检（supervisor/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_qa

router = APIRouter()
_sup = require_roles("supervisor", "admin")


# ── 评分卡 ────────────────────────────────────────────────────────────────


@router.get("/admin/api/v1/qa/scorecards")
async def list_scorecards(
    active_only: bool = Query(default=False),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"scorecards": await admin_qa.list_scorecards(active_only=active_only)}


class ScorecardIn(BaseModel):
    name: str
    items: list[dict[str, Any]]


@router.post("/admin/api/v1/qa/scorecards")
async def create_scorecard(
    body: ScorecardIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    sid = await admin_qa.create_scorecard(body.name, body.items)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="qa.scorecard.create",
        target_type="qa_scorecard",
        target_id=str(sid),
        detail={"name": body.name},
    )
    return {"ok": True, "id": sid}


class ScorecardPatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/qa/scorecards/{scorecard_id}")
async def patch_scorecard(
    scorecard_id: int, body: ScorecardPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await admin_qa.set_scorecard_active(scorecard_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="qa.scorecard.update",
        target_type="qa_scorecard",
        target_id=str(scorecard_id),
        detail={"active": body.active},
    )
    return {"ok": True}


# ── 质检记录 ──────────────────────────────────────────────────────────────


class ReviewIn(BaseModel):
    conversation_id: int
    scorecard_id: int
    score: int
    items_result: dict[str, Any]
    tags: str | None = None
    comment: str | None = None


@router.post("/admin/api/v1/qa/reviews")
async def submit_review(
    body: ReviewIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    rid = await admin_qa.submit_review(
        conversation_id=body.conversation_id,
        reviewer_staff_id=staff.get("sub", "unknown"),
        scorecard_id=body.scorecard_id,
        score=body.score,
        items_result=body.items_result,
        tags=body.tags,
        comment=body.comment,
    )
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="qa.review.submit",
        target_type="qa_review",
        target_id=str(rid),
        detail={"conversation_id": body.conversation_id, "score": body.score},
    )
    return {"ok": True, "id": rid}


@router.get("/admin/api/v1/qa/reviews")
async def list_reviews(
    conversation_id: int | None = Query(default=None),
    reviewer_staff_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {
        "reviews": await admin_qa.list_reviews(
            conversation_id=conversation_id,
            reviewer_staff_id=reviewer_staff_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    }
