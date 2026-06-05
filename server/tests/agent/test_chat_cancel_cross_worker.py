"""B2: 跨 worker cancel 必须经 Redis pub/sub 触达本地 cancel_evt。

场景：用户点"停止生成"→ DELETE /chat/{id}/stream 落到 worker A，但 stream 在 worker B。
本地 _cancel_signals dict 是进程内，不跨 worker。需要 Redis pub/sub 桥接。

测试覆盖：
- worker B 上 _listen_cancel_redis 订阅频道后，收到 publish 即 set cancel_evt
- listener task 收 task.cancel() 干净退出（不抛 non-CancelledError）
- settings.redis_url 未配 / _get_redis 返回 None → listener 立即退出，本地兜底语义
"""
import asyncio

import pytest

from ai_engine.api import chat as chat_api
from ai_engine.governance import rate_limit


@pytest.fixture
def _fake_redis(monkeypatch):
    """注入 fakeredis 作为 _get_redis 返回值。"""
    import fakeredis.aioredis

    fr = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rate_limit, "_get_redis", lambda: fr)
    return fr


async def test_redis_publish_sets_cancel_evt(_fake_redis):
    cancel_evt = asyncio.Event()
    conversation_id = 12345

    listener = asyncio.create_task(
        chat_api._listen_cancel_redis(conversation_id, cancel_evt)
    )
    # 给 subscriber 时间订阅；fakeredis 一般 <10ms 就绪
    await asyncio.sleep(0.05)

    # 模拟另一 worker DELETE → publish
    await _fake_redis.publish(f"cs:cancel:{conversation_id}", "1")

    # cancel_evt 应被 set（容许小延迟，最多 1s）
    await asyncio.wait_for(cancel_evt.wait(), timeout=1.0)
    assert cancel_evt.is_set()

    listener.cancel()
    try:
        await listener
    except asyncio.CancelledError:
        pass


async def test_listener_exits_on_task_cancel(_fake_redis):
    """listener task 收 task.cancel() 应干净退出，不抛 non-CancelledError。"""
    cancel_evt = asyncio.Event()
    listener = asyncio.create_task(chat_api._listen_cancel_redis(999, cancel_evt))
    await asyncio.sleep(0.05)  # 让它进入 subscribe loop
    listener.cancel()
    # 不应 hang，不应 raise non-CancelledError
    try:
        await asyncio.wait_for(listener, timeout=1.0)
    except asyncio.CancelledError:
        pass  # 预期


async def test_listener_exits_when_cancel_evt_already_set(_fake_redis):
    """cancel_evt 已 set 时 listener 进 loop 第一轮即退出，不无限订阅。"""
    cancel_evt = asyncio.Event()
    cancel_evt.set()
    # 应在 1.5s 内退出（pubsub.get_message 单次 timeout=1.0 + 一点容差）
    await asyncio.wait_for(
        chat_api._listen_cancel_redis(1, cancel_evt), timeout=1.5
    )


async def test_no_redis_fail_open(monkeypatch):
    """settings.redis_url 未配 → _get_redis 返回 None → listener 立刻退出，不报错。"""
    monkeypatch.setattr(rate_limit, "_get_redis", lambda: None)
    cancel_evt = asyncio.Event()
    # 不应 hang，立即返回
    await asyncio.wait_for(
        chat_api._listen_cancel_redis(1, cancel_evt), timeout=1.0
    )
    assert not cancel_evt.is_set()  # 没收到任何信号


async def test_publish_unknown_conv_does_not_trigger(_fake_redis):
    """publish 到别的 conversation_id 不应误触发本 evt（频道隔离）。"""
    cancel_evt = asyncio.Event()
    listener = asyncio.create_task(
        chat_api._listen_cancel_redis(111, cancel_evt)
    )
    await asyncio.sleep(0.05)

    # publish 到另一个 conv 的频道
    await _fake_redis.publish("cs:cancel:222", "1")
    await asyncio.sleep(0.1)
    assert not cancel_evt.is_set()

    listener.cancel()
    try:
        await listener
    except asyncio.CancelledError:
        pass
