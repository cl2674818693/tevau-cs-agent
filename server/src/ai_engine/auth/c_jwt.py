from typing import Any

import jwt
from fastapi import Header, HTTPException

from ai_engine.config import settings


def verify_app_jwt(token: str) -> dict[str, Any]:
    """验证 C 端 APP 签发的 JWT（RS256，本服务只验签）。spec §4.1：claims typ='c', sub=user_id。"""
    if not settings.app_jwt_public_key:
        raise ValueError("APP_JWT_PUBLIC_KEY not configured")
    try:
        # 算法白名单写死为非对称 RS256，不从可变配置读：
        # 否则误配 HS256 会把公开公钥当 HMAC 密钥，导致任意 token 伪造（alg-confusion）。
        claims = jwt.decode(token, settings.app_jwt_public_key, algorithms=["RS256"])
    except jwt.PyJWTError as e:
        raise ValueError(f"invalid jwt: {e}") from e
    if claims.get("typ") != "c":
        raise ValueError("not a C-side jwt")
    if not claims.get("sub"):
        raise ValueError("missing sub")
    return claims


async def require_c_user(authorization: str = Header(default="")) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing Bearer token")
    try:
        claims = verify_app_jwt(authorization[7:])
    except ValueError as e:
        raise HTTPException(401, str(e)) from e
    return str(claims["sub"])
