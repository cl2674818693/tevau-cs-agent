"""知识库管理（supervisor/engineer/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import knowledge

router = APIRouter()
_sup = require_roles("supervisor", "engineer", "admin")


class EntryIn(BaseModel):
    type: str
    key: str
    title: str
    content: str
    locale: str = "zh"


class FromGapIn(BaseModel):
    signal_key: str
    type: str
    key: str
    title: str
    content: str
    locale: str = "zh"


@router.get("/admin/api/v1/knowledge")
async def list_entries(
    type_: str | None = Query(default=None, alias="type"),
    status: str | None = Query(default=None),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"entries": await knowledge.list_entries(type_=type_, status=status)}


@router.post("/admin/api/v1/knowledge")
async def create_entry(
    body: EntryIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    if body.type not in ("api_doc", "error_code", "faq"):
        raise HTTPException(400, "invalid type")
    actor = str(staff.get("sub", "unknown"))
    eid = await knowledge.upsert_entry(
        type_=body.type, key=body.key, title=body.title,
        content=body.content, locale=body.locale, created_by=actor,
    )
    return {"ok": True, "id": eid}


@router.post("/admin/api/v1/knowledge/{entry_id}/submit")
async def submit_for_review(
    entry_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    """M4: draft → pending_review。"""
    await knowledge.submit_for_review(entry_id)
    return {"ok": True}


@router.post("/admin/api/v1/knowledge/{entry_id}/publish")
async def publish(entry_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await knowledge.publish(entry_id)
    return {"ok": True}


@router.delete("/admin/api/v1/knowledge/{entry_id}")
async def delete_entry(
    entry_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await knowledge.delete_entry(entry_id)
    return {"ok": True}


@router.post("/admin/api/v1/knowledge/from-gap")
async def from_gap(
    body: FromGapIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    if body.type not in ("api_doc", "error_code", "faq"):
        raise HTTPException(400, "invalid type")
    actor = str(staff.get("sub", "unknown"))
    eid = await knowledge.upsert_entry(
        type_=body.type, key=body.key, title=body.title,
        content=body.content, locale=body.locale,
        created_by=actor, source_gap_signal=body.signal_key,
    )
    return {"ok": True, "id": eid}
