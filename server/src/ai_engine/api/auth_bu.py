import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ai_engine.persistence.business_db import get_db

router = APIRouter()


class LoginIn(BaseModel):
    bu_id: str = Field(min_length=4, max_length=32, pattern=r"^BU[A-Za-z0-9]+$")


# 简易内存速率限制（生产换 Redis）
_RATE_BUCKET: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT = 5  # 5 次
RATE_WINDOW = 60  # 每 60s


def _check_rate(client_ip: str) -> bool:
    now = time.time()
    q = _RATE_BUCKET[client_ip]
    while q and q[0] < now - RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return False
    q.append(now)
    return True


@router.post("/api/v1/auth/bu/login")
async def bu_login(body: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    ip = (request.client.host if request.client else "?") or "?"
    if not _check_rate(ip):
        raise HTTPException(429, "too many attempts, please wait")

    # 查 BU 存在且 active（spec §4.1 简化方案）
    db = get_db("unlimitpay")
    row = await db.fetch_one("SELECT bu_id, status FROM bu WHERE bu_id=%s", (body.bu_id,))
    if not row or int(row.get("status") or 0) != 1:
        raise HTTPException(401, "主账户不存在或已禁用")  # 通用错误，防枚举

    # 签发 session cookie（HttpOnly + SameSite=Strict + 8h）。
    # secure 在生产置 True；本地 http 调试用 False 才能存住（spec §4.1）。
    response.set_cookie(
        key="ai_engine_session",
        value=body.bu_id,  # MVP-2 简化：cookie 直接装 bu_id；HMAC 签名见 MVP-3
        max_age=8 * 3600,
        httponly=True,
        secure=False,
        samesite="strict",
    )
    return {"ok": True, "bu_id": body.bu_id}


@router.post("/api/v1/auth/bu/logout")
async def bu_logout(response: Response) -> dict[str, Any]:
    response.delete_cookie("ai_engine_session")
    return {"ok": True}
