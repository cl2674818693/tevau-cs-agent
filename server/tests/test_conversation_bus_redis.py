"""会话事件总线的 Redis 跨副本桥接（spec §2 多副本）。

无 REDIS_URL 时走进程内队列（其余测试覆盖）；配置后，本进程 _publish 经 Redis 广播，
其他副本的进程级订阅桥把事件 fan-out 到本地订阅队列。带 origin 去重，避免自己发的回环双发。
"""

import asyncio
import json

import pytest


async def _make_bus_with_fakeredis(monkeypatch):
    pytest.importorskip("fakeredis")
    import fakeredis
    import fakeredis.aioredis

    monkeypatch.setenv("REDIS_URL", "redis://x:6379/0")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.api import staff_conversations as sc

    server = fakeredis.FakeServer()
    sc._redis = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
    sc._bridge_task = None
    return sc, server


async def test_redis_bridge_delivers_remote_event(monkeypatch):
    """另一副本发布的事件经 Redis 桥接到达本进程的本地订阅队列。"""
    sc, server = await _make_bus_with_fakeredis(monkeypatch)
    import fakeredis.aioredis

    cid = 555001
    q = sc.register_subscriber(cid)
    try:
        await sc.start_redis_bridge()
        await asyncio.sleep(0.1)  # 等桥的 psubscribe 就绪
        publisher = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        remote = {
            "o": "other-replica",
            "c": cid,
            "e": {"type": "human_message", "content": "来自副本B"},
        }
        await publisher.publish(f"conv:{cid}", json.dumps(remote))
        ev = await asyncio.wait_for(q.get(), timeout=2)
        assert ev["type"] == "human_message"
        assert ev["content"] == "来自副本B"
    finally:
        sc.unregister_subscriber(cid, q)
        if sc._bridge_task:
            sc._bridge_task.cancel()
        sc._bridge_task = None
        sc._redis = None


async def test_redis_bridge_skips_own_origin(monkeypatch):
    """本进程经 _publish 发的消息已本地投递，桥收到自己的 Redis 回环时跳过，不重复入队。"""
    sc, _ = await _make_bus_with_fakeredis(monkeypatch)

    cid = 555002
    q = sc.register_subscriber(cid)
    try:
        await sc.start_redis_bridge()
        await asyncio.sleep(0.1)
        # _publish 同步本地投递一次 + 异步 Redis 广播（origin 为本进程）
        sc._publish(cid, {"type": "human_message", "content": "only-once"})
        first = await asyncio.wait_for(q.get(), timeout=2)
        assert first["content"] == "only-once"
        # 桥若不按 origin 去重，会把自己的回环再投递一次 → 这里应超时（队列为空）
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.5)
    finally:
        sc.unregister_subscriber(cid, q)
        if sc._bridge_task:
            sc._bridge_task.cancel()
        sc._bridge_task = None
        sc._redis = None
