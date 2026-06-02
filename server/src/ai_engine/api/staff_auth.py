from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.config import settings
from ai_engine.persistence.staff import authenticate

router = APIRouter()


class StaffLoginIn(BaseModel):
    staff_id: str
    password: str


@router.post("/staff/api/v1/auth/login")
async def staff_login(body: StaffLoginIn) -> dict[str, Any]:
    # 配置缺失走 503（服务未就绪），运维更直观；避免让 issue_staff_token 裸抛 RuntimeError → 500。
    if not settings.staff_jwt_secret:
        raise HTTPException(503, "staff auth not configured")
    s = await authenticate(body.staff_id, body.password)
    if not s:
        raise HTTPException(401, "invalid credentials")
    token = issue_staff_token(s["staff_id"], s["role"])
    return {"token": token, "staff": s}
