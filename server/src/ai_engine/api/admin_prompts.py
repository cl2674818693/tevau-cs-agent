from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import prompt_changes as pc_mod
from ai_engine.persistence.insights import prompt_ab_stats
from ai_engine.prompts import registry

router = APIRouter()


def require_admin(staff: dict[str, Any] = Depends(require_staff)) -> dict[str, Any]:
    if staff.get("role") != "admin":
        raise HTTPException(403, "admin only")
    return staff


@router.get("/admin/api/v1/prompts/versions")
async def list_versions(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    registry.reload_registry()
    return {
        "versions": registry.list_versions(),
        "default": registry.default_version(),
        "rollout": registry.get_rollout(),
    }


class RolloutIn(BaseModel):
    rollout: dict[str, int]


@router.post("/admin/api/v1/prompts/rollout")
async def set_rollout(
    body: RolloutIn, admin: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    old_rollout = registry.get_rollout()
    try:
        registry.update_rollout(body.rollout)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    new_rollout = registry.get_rollout()
    actor: str = admin.get("sub", "unknown")
    await pc_mod.log_prompt_change(actor=actor, old_rollout=old_rollout, new_rollout=new_rollout)
    return {"ok": True, "rollout": new_rollout}


@router.get("/admin/api/v1/prompts/changes")
async def get_prompt_changes(
    _: dict[str, Any] = Depends(require_admin),
    limit: int = 50,
) -> dict[str, Any]:
    rows = await pc_mod.list_prompt_changes(limit=limit)
    return {"changes": rows}


@router.get("/admin/api/v1/prompts/ab-stats")
async def get_ab_stats(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    _: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """按 prompt_version 分组的 A/B 效果对比（admin 鉴权）。

    返回各版本的 assistant_turns / failed / failed_rate / downvote / downvote_rate。
    prompt_version IS NULL 的旧行不计入。
    downvote 通过 message_feedback.message_id JOIN messages 精确关联到版本。
    """
    versions = await prompt_ab_stats(date_from, date_to)
    return {"from": date_from, "to": date_to, "versions": versions}
