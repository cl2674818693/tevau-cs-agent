"""B-P0-3 跨 worker invalidate 同步：当一个 worker 拿到 revoke 通知后，必须广播给其他
worker 各自清自己的进程内 LRU 缓存，否则中毒会持续到本地 TTL 过期才消解。

实现：invalidate_c_token 在清本地的同时 publish 到 Redis 频道 `c_session:invalidate`；
所有 worker 启动时跑一个订阅协程 `start_c_session_invalidation_bridge`，收到消息后清本地。
"""

from unittest.mock import AsyncMock, patch

import pytest

from ai_engine.auth import c_session


@pytest.fixture(autouse=True)
def _clear():
    c_session._cache.clear()
    yield
    c_session._cache.clear()


class TestInvalidateBroadcast:
    async def test_invalidate_clears_local_and_publishes_to_redis(self) -> None:
        c_session._cache_put("tok-A", "U1", now=0)
        assert "tok-A" in c_session._cache
        fake = AsyncMock()
        with patch.object(c_session, "_get_invalidate_redis", return_value=fake):
            await c_session.invalidate_c_token("tok-A")
        assert "tok-A" not in c_session._cache
        # 必须 publish 到 c_session:invalidate 频道
        fake.publish.assert_awaited_once()
        args = fake.publish.await_args.args
        assert args[0] == "c_session:invalidate"
        assert args[1] == "tok-A"

    async def test_invalidate_when_no_redis_just_clears_local(self) -> None:
        c_session._cache_put("tok-B", "U2", now=0)
        with patch.object(c_session, "_get_invalidate_redis", return_value=None):
            await c_session.invalidate_c_token("tok-B")
        assert "tok-B" not in c_session._cache

    async def test_invalidate_redis_failure_does_not_raise(self) -> None:
        c_session._cache_put("tok-C", "U3", now=0)
        fake = AsyncMock()
        fake.publish.side_effect = ConnectionError("redis down")
        with patch.object(c_session, "_get_invalidate_redis", return_value=fake):
            # 不抛
            await c_session.invalidate_c_token("tok-C")
        # 即使 publish 失败，本地也必须先清
        assert "tok-C" not in c_session._cache
