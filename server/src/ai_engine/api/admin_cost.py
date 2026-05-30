"""Token 成本大盘（engineer/manager/admin）。pricing 更新落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_cost

router = APIRouter()
_view = require_roles("engineer", "manager", "admin")
_engineer = require_roles("engineer", "admin")  # pricing 编辑限工程/admin


@router.get("/admin/api/v1/cost/usage")
async def usage(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    user_type: str | None = Query(default=None),
    with_cost: bool = Query(default=False),
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    return {
        "items": await admin_cost.usage_by_model(
            date_from, date_to, user_type=user_type, with_cost=with_cost,
        )
    }


@router.get("/admin/api/v1/cost/pricing")
async def list_pricing(staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return {"items": await admin_cost.list_pricing()}


class PricingIn(BaseModel):
    model: str
    input_price_per_1k_x10000: int
    output_price_per_1k_x10000: int
    currency: str = "USD"


@router.put("/admin/api/v1/cost/pricing")
async def upsert_pricing(
    body: PricingIn, staff: dict[str, Any] = Depends(_engineer)
) -> dict[str, Any]:
    await admin_cost.upsert_pricing(
        body.model,
        body.input_price_per_1k_x10000,
        body.output_price_per_1k_x10000,
        body.currency,
    )
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"),
        action="cost.pricing.upsert",
        target_type="model_pricing",
        target_id=body.model,
        detail={
            "in": body.input_price_per_1k_x10000,
            "out": body.output_price_per_1k_x10000,
            "cur": body.currency,
        },
    )
    return {"ok": True}
