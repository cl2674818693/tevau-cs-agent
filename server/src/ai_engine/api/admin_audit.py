"""统一操作审计查询（engineer/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit

router = APIRouter()
_eng = require_roles("engineer", "admin")


@router.get("/admin/api/v1/audit")
async def list_audit(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    staff: dict[str, Any] = Depends(_eng),
) -> dict[str, Any]:
    entries = await admin_audit.list_admin_actions(
        actor=actor, action=action, target_type=target_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    return {"entries": entries}
