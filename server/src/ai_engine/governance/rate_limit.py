"""会话消息限流（spec §6.4 兜底层）：单 subject 每分钟消息数滑动窗口。

进程内内存滑动窗口，MVP 默认 30 条/分钟（settings.chat_rate_limit_per_min）。
多 worker 部署下各进程独立计数（MVP 可接受；需全局精确时换 Redis）。
"""

import time
from collections import defaultdict, deque

from ai_engine.config import settings

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


def check(key: str) -> tuple[bool, int]:
    """返回 (是否放行, 若拒绝则建议重试毫秒)。放行时记一次命中。"""
    limit = int(settings.chat_rate_limit_per_min)
    now = time.monotonic()
    dq = _hits[key]
    while dq and now - dq[0] >= _WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= limit:
        retry_after_ms = int((_WINDOW_SECONDS - (now - dq[0])) * 1000)
        return False, max(retry_after_ms, 0)
    dq.append(now)
    return True, 0


def reset() -> None:
    """测试用：清空窗口。"""
    _hits.clear()
