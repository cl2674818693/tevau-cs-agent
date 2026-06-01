"""Prompt 编辑/发布（engineer/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import prompt_drafts

router = APIRouter()
_eng = require_roles("engineer", "admin")


class DraftIn(BaseModel):
    version: str
    file_name: str
    content: str


@router.get("/admin/api/v1/prompt-editor")
async def list_drafts(
    version: str = Query(...),
    staff: dict[str, Any] = Depends(_eng),
) -> dict[str, Any]:
    return {"drafts": await prompt_drafts.list_by_version(version)}


@router.post("/admin/api/v1/prompt-editor")
async def create_draft(
    body: DraftIn, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    did = await prompt_drafts.create_draft(body.version, body.file_name, body.content, actor)
    return {"ok": True, "id": did}


@router.post("/admin/api/v1/prompt-editor/{draft_id}/publish")
async def publish_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    await prompt_drafts.publish(draft_id, actor)
    return {"ok": True}


@router.delete("/admin/api/v1/prompt-editor/{draft_id}")
async def delete_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await prompt_drafts.delete_draft(draft_id)
    return {"ok": True}
