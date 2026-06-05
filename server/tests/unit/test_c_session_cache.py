"""B-P0-3: C 端 Sa-Token 缓存的 LRU + 显式 invalidate（部分缓解 token 中毒）。

完整方案（Redis 共享 + revoke webhook）作为独立工程，本次落地：
- LRU 容量上限不被打爆；
- `invalidate_c_token(token)` 暴露给可能的 revoke 通知通路；
- 已过期项被读取时立刻清除（lazy expiration）。
"""

import time

import pytest

from ai_engine.auth import c_session


@pytest.fixture(autouse=True)
def _clear_cache():
    c_session._cache.clear()
    yield
    c_session._cache.clear()


class TestCacheLRU:
    async def test_invalidate_token_clears_entry(self) -> None:
        c_session._cache_put("tok-1", "U1", now=time.time())
        assert c_session._cache_get("tok-1", now=time.time()) == "U1"
        await c_session.invalidate_c_token("tok-1")
        assert c_session._cache_get("tok-1", now=time.time()) is None

    async def test_invalidate_unknown_token_is_noop(self) -> None:
        # 不抛
        await c_session.invalidate_c_token("never-seen")

    def test_expired_entry_returns_none_and_removed(self) -> None:
        c_session._cache_put("tok-old", "U1", now=time.time() - 10_000)
        # 立刻 get 应该已经过期（put 时 expire_at = now-10000 + TTL，已小于现在）
        assert c_session._cache_get("tok-old", now=time.time()) is None

    def test_cache_capacity_evicts_oldest(self, monkeypatch) -> None:
        # 临时把上限调小便于测试
        monkeypatch.setattr(c_session, "_CACHE_MAX", 3)
        now = time.time()
        for i in range(5):
            c_session._cache_put(f"tok-{i}", f"U{i}", now=now)
        # 最多保留 3 条；最早的两条应被驱逐
        assert len(c_session._cache) == 3
        assert c_session._cache_get("tok-0", now=now) is None
        assert c_session._cache_get("tok-1", now=now) is None
        assert c_session._cache_get("tok-4", now=now) == "U4"
