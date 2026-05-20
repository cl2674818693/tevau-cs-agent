from fastapi import Header, HTTPException, Request


async def require_bu(x_bu_id: str = Header(default="")) -> str:
    """MVP-1 简化：从 X-BU-ID header 读 bu_id（仅内网联调）。MVP-2 换主账户 ID 登录 + session。"""
    if not x_bu_id or not x_bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid X-BU-ID")
    return x_bu_id


async def resolve_identity(request: Request) -> tuple[str, str]:
    """从请求解析会话身份 → (user_type, subject_id)。

    spec §7.6 修订：反向 webhook 用会话身份解析（不硬性要求 Bearer）。
    MVP-2：B 端从 X-BU-ID header。C 端 JWT（cookie/bridge）在 task-05 接入后补充分支。
    """
    bu_id = request.headers.get("X-BU-ID", "")
    if bu_id.startswith("BU"):
        return "b", bu_id
    raise HTTPException(401, "unresolved identity")
