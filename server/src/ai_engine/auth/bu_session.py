import time

import jwt
from fastapi import HTTPException, Request

from ai_engine.auth.c_jwt import verify_app_jwt
from ai_engine.config import settings

# 会话身份类型（集中定义，避免散落字面量）
USER_TYPE_C = "c"  # C 端 APP 用户
USER_TYPE_B = "b"  # B 端 BU / 主账户
USER_TYPE_GUEST = "g"  # 未登录游客（匿名降级问答，仅通用问题）

SESSION_COOKIE = "ai_engine_session"
_SESSION_TTL = 8 * 3600


def issue_bu_session(bu_id: str) -> str:
    """签发 B 端 session token（HS256 签名，含 bu_id + 过期）。空密钥时拒绝签发。"""
    if not settings.bu_session_secret:
        raise RuntimeError("BU_SESSION_SECRET not configured")
    return jwt.encode(
        {"typ": "b", "sub": bu_id, "exp": int(time.time()) + _SESSION_TTL},
        settings.bu_session_secret,
        algorithm="HS256",
    )


def _verify_bu_session(token: str) -> str | None:
    """验签 session token，返回 bu_id；非法/过期/空密钥返回 None。"""
    if not settings.bu_session_secret:
        return None
    try:
        claims = jwt.decode(token, settings.bu_session_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "b":
        return None
    sub = claims.get("sub")
    return str(sub) if sub else None


def _bu_from_request(request: Request) -> str | None:
    """从签名 session cookie 解析 bu_id。仅 dev_trust_bu_header 开启时才回退信任 X-BU-ID。"""
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        bu_id = _verify_bu_session(cookie)
        if bu_id:
            return bu_id
    if settings.dev_trust_bu_header:
        return request.headers.get("X-BU-ID")
    return None


async def require_bu(request: Request) -> str:
    bu_id = _bu_from_request(request)
    if not bu_id or not bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid session")
    return bu_id


async def resolve_identity(request: Request) -> tuple[str, str]:
    """解析会话身份 → (user_type, subject_id)。优先级：C 端 Bearer JWT → B 端 cookie → 游客。

    spec §4.1：C 端 APP 经 JS Bridge 注入 JWT（Bearer）；B 端主账户 ID 登录后 session cookie。
    spec §7.6：反向 webhook 也用此身份解析（不硬性要求 Bearer）。
    未登录（无法解析出任何身份）时降级为游客（user_type=g）：仅通用问答，个人数据工具拒绝并引导登录。
    游客限流按前端持久化的 X-Guest-ID 隔离，缺失则归到 "anon"（弱隔离）。
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            claims = verify_app_jwt(auth[7:])
            return USER_TYPE_C, str(claims["sub"])
        except ValueError:
            pass  # 落到 B 端 / 游客
    bu_id = _bu_from_request(request)
    if bu_id and bu_id.startswith("BU"):
        return USER_TYPE_B, bu_id
    guest_id = request.headers.get("X-Guest-ID")
    return USER_TYPE_GUEST, f"guest:{guest_id or 'anon'}"
