"""AI 工具权限矩阵（engineer/admin）。写操作清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import tool_policies

router = APIRouter()
_eng = require_roles("engineer", "admin")


@router.get("/admin/api/v1/tool-policies")
async def list_policies(staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    return {"items": await tool_policies.list_all()}


class PolicyItem(BaseModel):
    tool_name: str
    role: str
    allowed: int = 0
    unmask_allowed: int = 0


class UpsertIn(BaseModel):
    items: list[PolicyItem]


@router.put("/admin/api/v1/tool-policies")
async def upsert(body: UpsertIn, staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    n = await tool_policies.upsert_many(
        actor=staff.get("sub", "unknown"),
        items=[it.model_dump() for it in body.items],
    )
    return {"ok": True, "count": n}
