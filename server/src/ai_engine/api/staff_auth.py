from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.persistence.staff import authenticate

router = APIRouter()


class StaffLoginIn(BaseModel):
    staff_id: str
    password: str


@router.post("/staff/api/v1/auth/login")
async def staff_login(body: StaffLoginIn) -> dict[str, Any]:
    s = await authenticate(body.staff_id, body.password)
    if not s:
        raise HTTPException(401, "invalid credentials")
    token = issue_staff_token(s["staff_id"], s["role"])
    return {"token": token, "staff": s}
