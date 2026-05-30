"""Prompt 编辑/发布（engineer/admin）。所有写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, prompt_drafts

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
    await admin_audit.log_admin_action(
        actor=actor,
        action="prompt.draft.create",
        target_type="prompt_draft",
        target_id=str(did),
        detail={"version": body.version, "file_name": body.file_name},
    )
    return {"ok": True, "id": did}


@router.post("/admin/api/v1/prompt-editor/{draft_id}/publish")
async def publish_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    await prompt_drafts.publish(draft_id, actor)
    await admin_audit.log_admin_action(
        actor=actor,
        action="prompt.publish",
        target_type="prompt_draft",
        target_id=str(draft_id),
    )
    return {"ok": True}


@router.delete("/admin/api/v1/prompt-editor/{draft_id}")
async def delete_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await prompt_drafts.delete_draft(draft_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")),
        action="prompt.draft.delete",
        target_type="prompt_draft",
        target_id=str(draft_id),
    )
    return {"ok": True}
