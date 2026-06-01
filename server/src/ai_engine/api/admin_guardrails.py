"""范围/拦截规则（engineer/admin）。写操作清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import guardrails

router = APIRouter()
_eng = require_roles("engineer", "admin")


class RuleIn(BaseModel):
    type: str
    pattern: str
    action: str = "block"


@router.get("/admin/api/v1/guardrails")
async def list_rules(staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    return {"rules": await guardrails.list_rules()}


@router.post("/admin/api/v1/guardrails")
async def create_rule(body: RuleIn, staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    try:
        rid = await guardrails.create_rule(body.type, body.pattern, body.action, actor)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    # toggle active
    active: int | None = None
    # content edits
    type: str | None = None
    pattern: str | None = None
    action: str | None = None


@router.patch("/admin/api/v1/guardrails/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    set_fields = body.model_dump(exclude_unset=True)
    if not set_fields:
        raise HTTPException(400, "no fields to update")
    # handle active toggle separately (existing behaviour)
    if "active" in set_fields and len(set_fields) == 1:
        await guardrails.set_active(rule_id, set_fields["active"])
        return {"ok": True}
    # content edit
    content_fields = {k: v for k, v in set_fields.items() if k != "active"}
    try:
        row = await guardrails.patch_rule(rule_id, content_fields)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if row is None:
        raise HTTPException(404, "rule not found")
    if "active" in set_fields:
        await guardrails.set_active(rule_id, set_fields["active"])
    return row


@router.delete("/admin/api/v1/guardrails/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await guardrails.delete_rule(rule_id)
    return {"ok": True}
