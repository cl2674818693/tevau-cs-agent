"""工具结果 Redis 缓存：相同 key 在 TTL 内只跑 handler 1 次。

仅 query_* 只读工具启用；create_ticket / mutating 工具不缓存。
用 fakeredis 替代真 Redis 避免外部依赖。
"""
import pytest

from ai_engine.agent import tool_router
from ai_engine.agent.tools import base as toolbase
from ai_engine.config import settings
from ai_engine.governance import rate_limit


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    """注入 fakeredis 替代真 Redis。"""
    import fakeredis.aioredis
    fr = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(rate_limit, "_get_redis", lambda: fr)
    monkeypatch.setattr(settings, "tool_cache_ttl_seconds", 30, raising=False)
    yield fr


@pytest.fixture(autouse=True)
def _no_db_audit(monkeypatch):
    """避免 log_tool_call 打真库。"""
    async def _noop(*_a, **_k):  # noqa: ANN002,ANN003
        return 0

    monkeypatch.setattr(tool_router, "log_tool_call", _noop)
    yield


@pytest.fixture
def _counted_tool():
    """注册 query_dummy 工具，记每次 handler 实际调用次数。"""
    calls = {"n": 0}

    async def _h(user_id: str = "u1") -> dict:
        calls["n"] += 1
        return {"value": calls["n"]}

    toolbase.register(toolbase.Tool(
        name="query_dummy",
        description="d",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        handler=_h,
        requires_subject_id=True,
        subject_field="user_id",
    ))
    try:
        yield calls
    finally:
        toolbase.REGISTRY.pop("query_dummy", None)


@pytest.fixture
def _mutating_tool():
    """create_ticket 风格的非 query_ 工具，handler 应每次都跑。"""
    calls = {"n": 0}

    async def _h(user_id: str = "u1") -> dict:
        calls["n"] += 1
        return {"value": calls["n"]}

    toolbase.register(toolbase.Tool(
        name="mutate_dummy",
        description="m",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        handler=_h,
        requires_subject_id=True,
        subject_field="user_id",
    ))
    try:
        yield calls
    finally:
        toolbase.REGISTRY.pop("mutate_dummy", None)


# C 端 user_id 已是纯数字 → tool_router 不查 _c_user_id_cache，直接注入
async def test_cache_hits_within_ttl(_counted_tool):
    """同 (tool, subject, params) → 2 次 dispatch 只跑 1 次 handler。"""
    r1 = await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    r2 = await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    assert r1["ok"] and r2["ok"]
    assert _counted_tool["n"] == 1
    assert r1["data"] == r2["data"]


async def test_cache_isolated_by_subject(_counted_tool):
    """不同 subject_id 不共享缓存。"""
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="111", conversation_id=1,
    )
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="222", conversation_id=1,
    )
    assert _counted_tool["n"] == 2


async def test_mutating_tool_not_cached(_mutating_tool):
    """非 query_* 前缀的工具一律穿透。"""
    await tool_router.dispatch(
        tool_name="mutate_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    await tool_router.dispatch(
        tool_name="mutate_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    assert _mutating_tool["n"] == 2


async def test_disabled_when_ttl_zero(_counted_tool, monkeypatch):
    monkeypatch.setattr(settings, "tool_cache_ttl_seconds", 0, raising=False)
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="123", conversation_id=1,
    )
    assert _counted_tool["n"] == 2


async def test_failure_not_cached():
    """handler 异常 → 失败结果不缓存，下次重试仍跑 handler。"""
    calls = {"n": 0}

    async def _boom(user_id: str = "u1") -> dict:
        calls["n"] += 1
        raise RuntimeError("boom")

    toolbase.register(toolbase.Tool(
        name="query_boom",
        description="b",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        handler=_boom,
        requires_subject_id=True,
        subject_field="user_id",
    ))
    try:
        r1 = await tool_router.dispatch(
            tool_name="query_boom", params={}, user_type="c", subject_id="123", conversation_id=1,
        )
        r2 = await tool_router.dispatch(
            tool_name="query_boom", params={}, user_type="c", subject_id="123", conversation_id=1,
        )
        assert r1["ok"] is False and r2["ok"] is False
        assert calls["n"] == 2, "failed result should not be cached"
    finally:
        toolbase.REGISTRY.pop("query_boom", None)
