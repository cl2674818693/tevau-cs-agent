"""B-P1-2: 跨副本事件总线 publish 的退避重试（与 signal_cancel 同样的可靠性目标）。

`_redis_publish` 是 fire-and-forget 任务；单次失败就丢消息会让多副本部署下的客服 SSE
偶发丢帧（用户消息/接管事件等核心事件）。改成 50/150/300ms 退避重试，最终失败仅 log，
不阻断 _publish 主链路（本地投递已先行）。
"""

from unittest.mock import AsyncMock, patch

import pytest

from ai_engine.api import staff_conversations as sc


class TestRedisPublishRetry:
    async def test_local_delivery_unaffected_by_redis_state(self) -> None:
        """无论 Redis 可达否，_deliver_local 都立刻投递本进程订阅者（不依赖 retry 结果）。"""
        q = sc.register_subscriber(42)
        try:
            with patch.object(sc, "_get_redis", return_value=None):
                sc._publish(42, {"type": "test", "x": 1})
            ev = q.get_nowait()
            assert ev["type"] == "test"
        finally:
            sc.unregister_subscriber(42, q)

    async def test_publish_retries_transient_failure(self) -> None:
        calls = {"n": 0}

        async def _flaky(_channel, _payload):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("transient")
            return 1

        fake = AsyncMock()
        fake.publish = _flaky
        with patch.object(sc, "_get_redis", return_value=fake):
            await sc._redis_publish(99, {"type": "user_message", "content": "hi"})
        assert calls["n"] >= 2, "publish should be retried at least once"

    async def test_publish_all_retries_failed_does_not_raise(self) -> None:
        async def _always_fail(_channel, _payload):
            raise ConnectionError("redis down")

        fake = AsyncMock()
        fake.publish = _always_fail
        with patch.object(sc, "_get_redis", return_value=fake):
            await sc._redis_publish(77, {"type": "mode_change"})
