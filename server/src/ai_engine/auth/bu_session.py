from fastapi import Header, HTTPException


async def require_bu(x_bu_id: str = Header(default="")) -> str:
    """MVP-1 简化：从 X-BU-ID header 读 bu_id（仅内网联调）。MVP-2 换主账户 ID 登录 + session。"""
    if not x_bu_id or not x_bu_id.startswith("BU"):
        raise HTTPException(401, "missing or invalid X-BU-ID")
    return x_bu_id
