"""B-P0-4: signal_cancel 在 Redis publish 失败时按退避重试，最终失败 fallback log。

确认：
- Redis publish 单次抖动失败时自动重试，最终成功 → 不漏跨 worker cancel；
- 重试全部失败时 swallow 异常不抛（不阻断 DELETE 主链路）；
- 本地 _cancel_signals 始终立刻 set（即使 Redis 完全不可用）。
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ai_engine.api import chat as chat_api


class TestSignalCancelRetry:
    async def test_local_evt_always_set_immediately(self) -> None:
        """无论 Redis 可达否，本地 cancel_evt 必须立刻 set —— 同 worker 流可立即退出。"""
        evt = asyncio.Event()
        chat_api._cancel_signals[12345] = evt
        try:
            with patch("ai_engine.governance.rate_limit._get_redis", return_value=None):
                await chat_api.signal_cancel(12345)
            assert evt.is_set()
        finally:
            chat_api._cancel_signals.pop(12345, None)

    async def test_redis_publish_retries_on_transient_failure(self, monkeypatch) -> None:
        """第一次失败、第二次成功 → 总共调 2 次 publish，不向上抛异常。"""
        calls = {"n": 0}

        async def _flaky_publish(_channel, _payload):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("transient")
            return 1

        fake_redis = AsyncMock()
        fake_redis.publish = _flaky_publish
        with patch("ai_engine.governance.rate_limit._get_redis", return_value=fake_redis):
            await chat_api.signal_cancel(99)
        assert calls["n"] >= 2, "publish should be retried at least once on transient failure"

    async def test_redis_publish_all_retries_failed_does_not_raise(
        self, monkeypatch
    ) -> None:
        """全部重试失败也不抛异常（DELETE 主链路必须 200/204）。"""

        async def _always_fail(_channel, _payload):
            raise ConnectionError("redis down")

        fake_redis = AsyncMock()
        fake_redis.publish = _always_fail
        with patch("ai_engine.governance.rate_limit._get_redis", return_value=fake_redis):
            # 不抛 → 测试 pass
            await chat_api.signal_cancel(77)
