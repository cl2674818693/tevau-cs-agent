"""会话路由规则（supervisor/admin）。写操作清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import routing_rules

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/routing-rules")
async def list_rules(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"rules": await routing_rules.list_rules()}


class RuleIn(BaseModel):
    match_type: str
    match_value: str
    target_group_id: int
    priority: int = 100


@router.post("/admin/api/v1/routing-rules")
async def create_rule(body: RuleIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    try:
        rid = await routing_rules.create_rule(
            body.match_type, body.match_value, body.target_group_id, body.priority,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    # toggle active
    active: int | None = None
    # content edits
    priority: int | None = None
    match_type: str | None = None
    match_value: str | None = None
    target_group_id: int | None = None


@router.patch("/admin/api/v1/routing-rules/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    set_fields = body.model_dump(exclude_unset=True)
    if not set_fields:
        raise HTTPException(400, "no fields to update")
    # handle active toggle separately (existing behaviour)
    if "active" in set_fields and len(set_fields) == 1:
        await routing_rules.set_active(rule_id, set_fields["active"])
        return {"ok": True}
    # content edit (excludes active)
    content_fields = {k: v for k, v in set_fields.items() if k != "active"}
    try:
        row = await routing_rules.patch_rule(rule_id, content_fields)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if row is None:
        raise HTTPException(404, "rule not found")
    # also handle active if present alongside content fields
    if "active" in set_fields:
        await routing_rules.set_active(rule_id, set_fields["active"])
    return row


@router.delete("/admin/api/v1/routing-rules/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await routing_rules.delete_rule(rule_id)
    return {"ok": True}
