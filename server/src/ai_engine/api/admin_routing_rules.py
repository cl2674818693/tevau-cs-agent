"""会话路由规则（supervisor/admin）。写操作落审计 + 清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, routing_rules

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
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="routing_rule.create",
        target_type="routing_rule",
        target_id=str(rid),
        detail=body.model_dump(),
    )
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/routing-rules/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await routing_rules.set_active(rule_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="routing_rule.update",
        target_type="routing_rule",
        target_id=str(rule_id),
        detail={"active": body.active},
    )
    return {"ok": True}


@router.delete("/admin/api/v1/routing-rules/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await routing_rules.delete_rule(rule_id)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="routing_rule.delete",
        target_type="routing_rule",
        target_id=str(rule_id),
    )
    return {"ok": True}
