from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_staff
from ai_engine.prompts import registry

router = APIRouter()


def require_admin(staff: dict[str, Any] = Depends(require_staff)) -> dict[str, Any]:
    if staff.get("role") != "admin":
        raise HTTPException(403, "admin only")
    return staff


@router.get("/admin/api/v1/prompts/versions")
async def list_versions(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    registry.reload_registry()
    return {
        "versions": registry.list_versions(),
        "default": registry.default_version(),
        "rollout": registry.get_rollout(),
    }


class RolloutIn(BaseModel):
    rollout: dict[str, int]


@router.post("/admin/api/v1/prompts/rollout")
async def set_rollout(
    body: RolloutIn, _: dict[str, Any] = Depends(require_admin)
) -> dict[str, Any]:
    try:
        registry.update_rollout(body.rollout)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "rollout": registry.get_rollout()}
