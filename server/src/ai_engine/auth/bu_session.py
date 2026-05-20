from fastapi import HTTPException, Request


def _bu_from_request(request: Request) -> str | None:
    """优先 session cookie（task-04 登录签发）；回退 X-BU-ID header（内网/联调，MVP-3 移除）。"""
    return request.cookies.get("ai_engine_session") or request.headers.get("X-BU-ID")


async def require_bu(request: Request) -> str:
    bu_id = _bu_from_request(request)
    if not bu_id or not bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid session")
    return bu_id


async def resolve_identity(request: Request) -> tuple[str, str]:
    """从请求解析会话身份 → (user_type, subject_id)。

    spec §7.6 修订：反向 webhook 用会话身份解析（不硬性要求 Bearer）。
    MVP-2：B 端 session cookie（回退 X-BU-ID）。C 端 JWT 在 task-05 接入后补。
    """
    bu_id = _bu_from_request(request)
    if bu_id and bu_id.startswith("BU"):
        return "b", bu_id
    raise HTTPException(401, "unresolved identity")
