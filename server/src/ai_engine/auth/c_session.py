"""C 端 APP 用户身份解析。

APP 经 JS Bridge 注入 Sa-Token（随机 UUID，非 JWT，本服务无法本地验签），前端放进
`Authorization: Bearer <token>`。本模块拿裸 token 调 C 端 gateway 的 getCurrentUserInfo
换取用户身份（userCode），失败即视为未登录。原 RS256 JWT 验签方案（c_jwt）已作废。
"""

import asyncio
import logging
import time
from collections import OrderedDict
from typing import TYPE_CHECKING

import httpx

from ai_engine.config import settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# B-P0-3 跨 worker invalidate 同步用频道。任一 worker 收到 revoke 通知 → 清自己本地
# LRU + publish 到此频道；其他 worker 的桥接协程订阅后也清自己本地。
_INVALIDATE_CHANNEL = "c_session:invalidate"
_invalidate_redis: "Redis | None" = None
_invalidate_bridge_task: "asyncio.Task[None] | None" = None


def _get_invalidate_redis() -> "Redis | None":
    """复用 conversation bus 同一 Redis 连接池语义（按 settings.redis_url 懒初始化）。"""
    global _invalidate_redis
    if not settings.redis_url:
        return None
    if _invalidate_redis is None:
        import redis.asyncio as aioredis

        _invalidate_redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _invalidate_redis

# token -> (user_code, expire_at)；成功结果短期缓存，避免每个请求都打一次远程校验。
# B-P0-3: 用 OrderedDict 做 LRU，硬上限 _CACHE_MAX 防长期累积无界增长；
# 暴露 invalidate_c_token 以便未来 revoke 通知通道清除特定 token。
# 完整跨 worker 共享缓存 + Redis revoke 推送作为独立工程跟进。
_cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
_CACHE_MAX = 1024


def _cache_get(token: str, now: float) -> str | None:
    hit = _cache.get(token)
    if hit is None:
        return None
    if hit[1] <= now:
        # lazy expiration：被读到已过期就立刻清掉，下次重走 gateway 校验
        _cache.pop(token, None)
        return None
    _cache.move_to_end(token)  # LRU touch
    return hit[0]


def _cache_put(token: str, user_code: str, now: float) -> None:
    if token in _cache:
        _cache.pop(token)
    _cache[token] = (user_code, now + settings.c_identity_cache_ttl)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)  # 驱逐最旧（LRU）


async def invalidate_c_token(token: str) -> None:
    """显式清除某 token 的缓存 + 跨 worker 广播。

    B-P0-3：调用顺序保证"本地先清，再 publish 广播"——本进程立刻见效，不依赖 Redis；
    其他 worker 通过订阅 `_INVALIDATE_CHANNEL` 同步清自己本地缓存（消除中毒持续时长）。
    Redis 不可达 fail-open，仅日志记录不抛错。
    """
    _cache.pop(token, None)
    client = _get_invalidate_redis()
    if client is None:
        return
    try:
        await client.publish(_INVALIDATE_CHANNEL, token)
    except Exception:
        logger.warning("c_session invalidate publish failed", exc_info=True)


async def _invalidate_bridge() -> None:
    """订阅跨 worker invalidate 广播；收到 token 后清本地缓存。"""
    client = _get_invalidate_redis()
    if client is None:
        return
    pubsub = client.pubsub()
    await pubsub.subscribe(_INVALIDATE_CHANNEL)
    async for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        token = msg.get("data")
        if isinstance(token, str):
            _cache.pop(token, None)


async def start_c_session_invalidation_bridge() -> None:
    """应用启动时调用：配置 Redis 时拉起进程级订阅桥，让 worker 间 invalidate 同步。"""
    global _invalidate_bridge_task
    if _get_invalidate_redis() is not None and _invalidate_bridge_task is None:
        _invalidate_bridge_task = asyncio.create_task(_invalidate_bridge())


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
