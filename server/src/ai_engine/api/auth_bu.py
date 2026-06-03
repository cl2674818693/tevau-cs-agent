import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ai_engine.auth.bu_session import SESSION_COOKIE, issue_bu_session
from ai_engine.i18n import t as _t
from ai_engine.persistence.business_db import get_db


def _accept_language(request: Request) -> str | None:
    """从 Accept-Language header 取首个偏好语言（"en-US,en;q=0.9,zh-CN;q=0.8" → "en-US"）。
    B 端登录页通常是浏览器调起 → 走浏览器语言；APP 端不调登录直接 cookie，不会经过此路径。
    返回 None 时 t() 自动回退 en（符合 B 端默认 en 约定）。"""
    header = request.headers.get("accept-language")
    if not header:
        return None
    return header.split(",")[0].strip()

router = APIRouter()


class LoginIn(BaseModel):
    # 主账户 ID = nexus 真实租户 tenant_id（数字串，如 1011010000068）。
    # 字段名保留 bu_id 不破坏前端契约，值语义已是 tenant_id。
    bu_id: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9]+$")


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

    # 校验主账户身份：查 nexus 真实租户主表 t_nexus_company_info（按 tenant_id）。
    # status: 0待开启 1运行中 2已停用；仅拒绝「已停用」与「未配置(NULL)」。
    # 修复：原 `int(row.get("status") or 0)` 会把 NULL 当 0 通过，
    # 导致脏数据/未初始化租户全部能登。NULL 视为"租户未配置完毕"显式拒登。
    locale = _accept_language(request)
    db = get_db("nexus")
    row = await db.fetch_one(
        "SELECT tenant_id, status FROM t_nexus_company_info WHERE tenant_id=%s AND del_flag=0",
        (body.bu_id,),
    )
    if not row:
        raise HTTPException(401, _t("auth.tenant_invalid", locale))  # 通用错误，防枚举
    status_val = row.get("status")
    if status_val is None:
        raise HTTPException(401, _t("auth.tenant_invalid", locale))
    if int(status_val) == 2:
        raise HTTPException(401, _t("auth.tenant_invalid", locale))

    # 签发签名 session cookie（HttpOnly + SameSite=Strict + 8h）。
    # cookie 值是 HS256 签名 token（含 bu_id + 过期），服务端验签，无法伪造。
    # secure 在生产置 True；本地 http 调试用 False 才能存住（spec §4.1）。
    response.set_cookie(
        key=SESSION_COOKIE,
        value=issue_bu_session(body.bu_id),
        max_age=8 * 3600,
        httponly=True,
        secure=False,
        samesite="strict",
    )
    return {"ok": True, "bu_id": body.bu_id}


@router.post("/api/v1/auth/bu/logout")
async def bu_logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
