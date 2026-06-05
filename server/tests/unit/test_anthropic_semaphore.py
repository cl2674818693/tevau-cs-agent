"""Anthropic 调用 Semaphore 护栏。

超载场景：信号量为 1 时，第 2 个并发调用必须在 acquire 超时（settings.llm_acquire_timeout）
内返回 SystemBusy 异常，而不是阻塞等待 LLM 调用本身。
"""
import asyncio
import pytest

from ai_engine.integrations import anthropic_client as ac
from ai_engine.config import settings


@pytest.fixture(autouse=True)
def _tight_sem(monkeypatch):
    monkeypatch.setattr(settings, "llm_max_concurrency", 1, raising=False)
    monkeypatch.setattr(settings, "llm_acquire_timeout_seconds", 0.05, raising=False)
    ac._rebuild_llm_semaphore()
    yield


async def test_semaphore_busy_raises_quickly(monkeypatch):
    async def slow_stream(text):
        await asyncio.sleep(1.0)
        return "yes"

    # 让 _client.messages.create 返回一个慢 awaitable
    async def slow_create(**_):
        await asyncio.sleep(1.0)
        # 模拟一个最简 response 对象
        class R:
            content = []
        return R()

    monkeypatch.setattr(ac._client.messages, "create", slow_create)

    async def call():
        return await ac.classify_topic("hello")

    first = asyncio.create_task(call())
    await asyncio.sleep(0.01)
    with pytest.raises(ac.SystemBusy):
        await call()
    first.cancel()
    try:
        await first
    except (asyncio.CancelledError, BaseException):
        pass


async def test_semaphore_release_allows_next(monkeypatch):
    async def quick_create(**_):
        class R:
            content = [type("B", (), {"text": "yes"})()]
        return R()
    monkeypatch.setattr(ac._client.messages, "create", quick_create)
    r1 = await ac.classify_topic("a")
    r2 = await ac.classify_topic("b")
    assert r1 == "yes" and r2 == "yes"
