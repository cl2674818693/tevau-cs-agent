import time
from typing import Any

import jwt
from fastapi import Header, HTTPException

from ai_engine.config import settings


def issue_staff_token(staff_id: str, role: str) -> str:
    if not settings.staff_jwt_secret:
        raise RuntimeError("STAFF_JWT_SECRET not configured")
    return jwt.encode(
        {"typ": "staff", "sub": staff_id, "role": role, "exp": int(time.time()) + 8 * 3600},
        settings.staff_jwt_secret,
        algorithm="HS256",
    )


def verify_staff_token(token: str) -> dict[str, Any]:
    # 空密钥时直接拒绝：否则 HS256 用空串签名，攻击者可自签 admin token
    if not settings.staff_jwt_secret:
        raise ValueError("staff auth not configured")
    try:
        claims = jwt.decode(token, settings.staff_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError(str(e)) from e
    if claims.get("typ") != "staff":
        raise ValueError("not staff token")
    return claims


async def require_staff(authorization: str = Header(default="")) -> dict[str, Any]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing staff token")
    try:
        return verify_staff_token(authorization[7:])
    except ValueError as e:
        raise HTTPException(401, str(e)) from e
