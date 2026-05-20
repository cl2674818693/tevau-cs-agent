from fastapi import HTTPException, Request

from ai_engine.auth.c_jwt import verify_app_jwt


def _bu_from_request(request: Request) -> str | None:
    """优先 session cookie（task-04 登录签发）；回退 X-BU-ID header（内网/联调，MVP-3 移除）。"""
    return request.cookies.get("ai_engine_session") or request.headers.get("X-BU-ID")


async def require_bu(request: Request) -> str:
    bu_id = _bu_from_request(request)
    if not bu_id or not bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid session")
    return bu_id


async def resolve_identity(request: Request) -> tuple[str, str]:
    """解析会话身份 → (user_type, subject_id)。C 端 Bearer JWT 优先，否则 B 端 cookie/X-BU-ID。

    spec §4.1：C 端 APP 经 JS Bridge 注入 JWT（Bearer）；B 端主账户 ID 登录后 session cookie。
    spec §7.6：反向 webhook 也用此身份解析（不硬性要求 Bearer）。
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            claims = verify_app_jwt(auth[7:])
            return "c", str(claims["sub"])
        except ValueError:
            pass  # 落到 B 端
    bu_id = _bu_from_request(request)
    if bu_id and bu_id.startswith("BU"):
        return "b", bu_id
    raise HTTPException(401, "unresolved identity")
