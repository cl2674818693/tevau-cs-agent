"""范围/拦截规则（engineer/admin）。写操作落审计 + 清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, guardrails

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
    await admin_audit.log_admin_action(
        actor=actor, action="guardrail.create",
        target_type="guardrail", target_id=str(rid), detail=body.model_dump(),
    )
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/guardrails/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await guardrails.set_active(rule_id, body.active)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="guardrail.update",
        target_type="guardrail", target_id=str(rule_id), detail={"active": body.active},
    )
    return {"ok": True}


@router.delete("/admin/api/v1/guardrails/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await guardrails.delete_rule(rule_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="guardrail.delete",
        target_type="guardrail", target_id=str(rule_id),
    )
    return {"ok": True}
