"""会话消息限流（spec §6.4 兜底层）：单 subject 每分钟消息数滑动窗口。

配置 REDIS_URL 时用 Redis 做全局精确滑动窗口（多副本一致）；未配置时回退进程内内存窗口
（单副本 / 测试足够）。Redis 故障时 fail-open（放行）并落本地窗口兜底，避免限流层拖垮服务。
"""

import logging
import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from ai_engine.config import settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60.0
_WINDOW_MS = 60_000
_hits: dict[str, deque[float]] = defaultdict(deque)

# 原子滑动窗口：清理过期 → 计数 → 满则算重试毫秒，否则记一次。member 由调用方传唯一值。
_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local earliest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = window - (now - tonumber(earliest[2]))
  if retry < 0 then retry = 0 end
  return {0, retry}
end
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
return {1, 0}
"""

_redis: "Redis | None" = None  # lazy 异步客户端


def _get_redis() -> "Redis | None":
    global _redis
    if not settings.redis_url:
        return None
    if _redis is None:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _local_check(key: str, limit: int) -> tuple[bool, int]:
    # limit<=0 直接拒（且无重试建议）：避免空 dq 取 dq[0] IndexError，并语义上"零额度=永拒"。
    if limit <= 0:
        return False, 0
    now = time.monotonic()
    dq = _hits[key]
    while dq and now - dq[0] >= _WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= limit:
        retry_after_ms = int((_WINDOW_SECONDS - (now - dq[0])) * 1000)
        return False, max(retry_after_ms, 0)
    dq.append(now)
    return True, 0


async def check(key: str) -> tuple[bool, int]:
    """返回 (是否放行, 若拒绝则建议重试毫秒)。放行时记一次命中。"""
    limit = int(settings.chat_rate_limit_per_min)
    client = _get_redis()
    if client is None:
        return _local_check(key, limit)
    try:
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}-{time.perf_counter_ns()}"
        allowed, retry = await client.eval(  # type: ignore[misc]
            _LUA, 1, f"rl:{key}", now_ms, _WINDOW_MS, limit, member
        )
        return bool(int(allowed)), int(retry)
    except Exception:  # redis 故障：fail-open，落进程内窗口兜底，不阻断主链路
        logger.warning("rate_limit redis unavailable, falling back to local window", exc_info=True)
        return _local_check(key, limit)


def reset() -> None:
    """测试用：清空进程内窗口。"""
    _hits.clear()
