"""SLA 配置与告警（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_sla

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/sla/policies")
async def list_policies(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"policies": await admin_sla.list_policies()}


class PolicyIn(BaseModel):
    metric: str
    threshold_seconds: int
    scope: str = "all"
    scope_value: str | None = None


@router.post("/admin/api/v1/sla/policies")
async def create_policy(body: PolicyIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    try:
        pid = await admin_sla.create_policy(
            body.metric, body.threshold_seconds, body.scope, body.scope_value
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": pid}


class PolicyPatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/sla/policies/{policy_id}")
async def patch_policy(
    policy_id: int, body: PolicyPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await admin_sla.set_policy_active(policy_id, body.active)
    return {"ok": True}


@router.delete("/admin/api/v1/sla/policies/{policy_id}")
async def delete_policy(policy_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await admin_sla.delete_policy(policy_id)
    return {"ok": True}


@router.get("/admin/api/v1/sla/breaches")
async def list_breaches(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"breaches": await admin_sla.compute_breaches()}
