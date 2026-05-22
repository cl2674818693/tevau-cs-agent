import pytest


async def test_redis_sliding_window_global_count(monkeypatch):
    """配置 REDIS_URL 时走 Redis 滑动窗口：超阈值拒绝、返回重试毫秒，不同 key 独立计数。"""
    pytest.importorskip("fakeredis")
    import fakeredis.aioredis

    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    monkeypatch.setenv("CHAT_RATE_LIMIT_PER_MIN", "3")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance import rate_limit

    rate_limit._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        results = [await rate_limit.check("b:BUX") for _ in range(5)]
        assert [allowed for allowed, _ in results] == [True, True, True, False, False]
        assert results[3][1] > 0  # 拒绝时返回建议重试毫秒
        ok, _ = await rate_limit.check("b:BUY")  # 独立 key 不受影响
        assert ok is True
    finally:
        rate_limit._redis = None


async def test_redis_failure_fails_open(monkeypatch):
    """Redis 故障时 fail-open（放行），不阻断主链路。"""
    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance import rate_limit

    class _Boom:
        async def eval(self, *a, **k):
            raise RuntimeError("redis down")

    rate_limit._redis = _Boom()
    rate_limit.reset()
    try:
        ok, _ = await rate_limit.check("b:BUZ")
        assert ok is True
    finally:
        rate_limit._redis = None
