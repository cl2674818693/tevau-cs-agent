"""C 端 APP 用户身份解析。

APP 经 JS Bridge 注入 Sa-Token（随机 UUID，非 JWT，本服务无法本地验签），前端放进
`Authorization: Bearer <token>`。本模块拿裸 token 调 C 端 gateway 的 getCurrentUserInfo
换取用户身份（userCode），失败即视为未登录。原 RS256 JWT 验签方案（c_jwt）已作废。
"""

import logging
import time

import httpx

from ai_engine.config import settings

logger = logging.getLogger(__name__)

# token -> (user_code, expire_at)；成功结果短期缓存，避免每个请求都打一次远程校验
_cache: dict[str, tuple[str, float]] = {}


def _cache_get(token: str, now: float) -> str | None:
    hit = _cache.get(token)
    if hit and hit[1] > now:
        return hit[0]
    return None


def _cache_put(token: str, user_code: str, now: float) -> None:
    # 顺手清理过期项，避免长期累积失效 token
    if len(_cache) > 1024:
        for k in [k for k, (_, exp) in _cache.items() if exp <= now]:
            _cache.pop(k, None)
    _cache[token] = (user_code, now + settings.c_identity_cache_ttl)


async def resolve_c_user(token: str) -> str | None:
    """用 APP 注入的 Sa-Token 调 C 端 gateway getCurrentUserInfo 换取 userCode。

    返回 userCode（C 端用户唯一标识，作 subject_id）；token 无效/网络失败返回 None。
    """
    if not token:
        return None
    now = time.time()
    cached = _cache_get(token, now)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=settings.c_identity_timeout_seconds) as client:
            resp = await client.post(
                f"{settings.c_app_api_base}/user/getCurrentUserInfo",
                json={},
                headers={
                    # APP 的 Sa-Token 直接放 Authorization（裸 token，不加 Bearer 前缀）
                    "Authorization": token,
                    "Content-Type": "application/json",
                    "version": settings.c_app_api_version,
                },
            )
    except Exception:
        logger.warning("c getCurrentUserInfo request failed", exc_info=True)
        return None
    if resp.status_code != 200:
        logger.warning("c getCurrentUserInfo non-200: status=%s", resp.status_code)
        return None
    try:
        body = resp.json()
    except ValueError:
        logger.warning("c getCurrentUserInfo non-json body")
        return None
    if body.get("code") != 0:  # token 失效/未登录：gateway 返回非 0 code
        return None
    user_code = (body.get("data") or {}).get("userCode")
    if not user_code:
        logger.warning("c getCurrentUserInfo missing userCode")
        return None
    _cache_put(token, str(user_code), now)
    return str(user_code)
