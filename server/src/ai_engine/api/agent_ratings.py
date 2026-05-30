"""客服满意度：C/B 端用户提交 + 后台聚合查询。

用户端鉴权：B 端走 DEV_TRUST_BU_HEADER（测试/B 端）或 bu_session；C 端走 c_session（若存在）。
本文件用一个最小 _resolve_subject 内联依赖：先尝试 BU header，再尝试 C session。
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import agent_ratings, db

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


async def _resolve_subject(
    request: Request, x_bu_id: str = Header(default="")
) -> tuple[str, str]:
    """返回 (subject_id, user_type)。生产请按项目鉴权配置完善 C 端走 c_session 的分支。"""
    from ai_engine.config import settings

    if settings.dev_trust_bu_header and x_bu_id:
        return x_bu_id, "b"
    # C 端：尝试从 c_session 读 userCode（按项目现有方式；空则 401）
    try:
        from ai_engine.auth.c_session import resolve_subject_from_request  # type: ignore

        subj = await resolve_subject_from_request(request)
        if subj:
            return subj, "c"
    except ImportError:
        pass
    raise HTTPException(401, "no subject")


async def _conv_belongs_to(subject_id: str, user_type: str, conv_id: int) -> bool:
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM conversations WHERE id = :id AND subject_id = :s AND user_type = :ut",
        {"id": conv_id, "s": subject_id, "ut": user_type},
    )
    return row is not None


async def _conv_assigned_staff(conv_id: int) -> str | None:
    row = await db.fetch_one(
        "SELECT assigned_staff_id, mode FROM conversations WHERE id = :id",
        {"id": conv_id},
    )
    if row is None:
        return None
    if row["assigned_staff_id"]:
        return str(row["assigned_staff_id"])
    # 若 assigned 已清空，回退到最近一次 take 的 staff
    take = await db.fetch_one(
        "SELECT staff_id FROM staff_actions WHERE conversation_id = :cid AND action = 'take' "
        "ORDER BY id DESC LIMIT 1",
        {"cid": conv_id},
    )
    return str(take["staff_id"]) if take else None


@router.get("/api/v1/conversations/{conv_id}/agent-rating/eligibility")
async def eligibility(
    conv_id: int,
    request: Request,
    x_bu_id: str = Header(default=""),
) -> dict[str, Any]:
    subj, ut = await _resolve_subject(request, x_bu_id)
    if not await _conv_belongs_to(subj, ut, conv_id):
        raise HTTPException(403, "not your conversation")
    staff_id = await _conv_assigned_staff(conv_id)
    if not staff_id:
        return {"eligible": False, "already_rated": False, "staff_id": None}
    existing = await agent_ratings.get_for_conversation(conv_id, subj)
    return {
        "eligible": True,
        "already_rated": existing is not None,
        "staff_id": staff_id,
    }


class RatingIn(BaseModel):
    rating: int
    comment: str | None = None


@router.post("/api/v1/conversations/{conv_id}/agent-rating")
async def submit(
    conv_id: int,
    body: RatingIn,
    request: Request,
    x_bu_id: str = Header(default=""),
) -> dict[str, Any]:
    subj, ut = await _resolve_subject(request, x_bu_id)
    if not await _conv_belongs_to(subj, ut, conv_id):
        raise HTTPException(403, "not your conversation")
    staff_id = await _conv_assigned_staff(conv_id)
    if not staff_id:
        raise HTTPException(400, "no agent assigned")
    existing = await agent_ratings.get_for_conversation(conv_id, subj)
    if existing is not None:
        raise HTTPException(409, "already rated")
    try:
        rid = await agent_ratings.record(
            conversation_id=conv_id,
            staff_id=staff_id,
            subject_id=subj,
            user_type=ut,
            rating=body.rating,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": rid}


# ── 后台聚合 ──────────────────────────────────────────────────────────────


@router.get("/admin/api/v1/agent-ratings")
async def admin_list(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    items = await agent_ratings.list_for_admin(
        staff_id=staff_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    aggregate = {"count": 0, "avg_rating": 0.0}
    if staff_id:
        aggregate = await agent_ratings.aggregate_by_staff(staff_id, date_from, date_to)
    return {"items": items, "aggregate": aggregate}
