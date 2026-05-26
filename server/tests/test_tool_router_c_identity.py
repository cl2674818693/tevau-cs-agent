"""C 端身份注入：会话 subject_id 是 gateway 的 userCode（如 U43825474），但业务库各表
按数字 user_id 隔离。dispatch 必须把 userCode 翻成数字 id 再注入工具，否则 WHERE
user_id='U...' 永远查空（线上现象：KYC/流水全查不到）。"""
import pytest

pytestmark = pytest.mark.asyncio


async def _register_fake(name):
    from ai_engine.agent.tools import base

    received = {}

    async def fake_handler(user_id: str, **kwargs):
        received["user_id"] = user_id
        return {"user_id": user_id}

    base.register(
        base.Tool(
            name=name,
            description="fake",
            input_schema={"type": "object", "properties": {}},
            handler=fake_handler,
            requires_subject_id=True,
            subject_field="user_id",
            supports_unmask=False,
        )
    )
    return received


async def test_c_user_code_translated_to_numeric_id(temp_db_url, monkeypatch):
    from ai_engine.agent import tool_router
    from ai_engine.persistence.db import init_db

    await init_db()
    received = await _register_fake("query_c_xlate")

    class FakeDB:
        async def fetch_one(self, sql, params=()):
            assert "user_code" in sql and params == ("U43825474",)
            return {"id": 212433}

    monkeypatch.setattr(tool_router, "get_db", lambda name: FakeDB())
    tool_router._c_user_id_cache.clear()

    result = await tool_router.dispatch(
        tool_name="query_c_xlate", params={}, user_type="c",
        subject_id="U43825474", conversation_id=1,
    )
    assert result["ok"] is True
    assert received["user_id"] == "212433"  # userCode 已翻成数字 id，不是裸 userCode


async def test_c_unmapped_user_code_errors_not_empty(temp_db_url, monkeypatch):
    from ai_engine.agent import tool_router
    from ai_engine.persistence.db import init_db

    await init_db()
    await _register_fake("query_c_unmapped")

    class FakeDB:
        async def fetch_one(self, sql, params=()):
            return None  # 业务库找不到该 userCode

    monkeypatch.setattr(tool_router, "get_db", lambda name: FakeDB())
    tool_router._c_user_id_cache.clear()

    result = await tool_router.dispatch(
        tool_name="query_c_unmapped", params={}, user_type="c",
        subject_id="UNKNOWN_CODE", conversation_id=1,
    )
    assert result["ok"] is False  # 明确报错，不静默查空


async def test_b_subject_not_translated(temp_db_url, monkeypatch):
    # B 端 subject_id 是 tenant_id，直接用，不走 userCode→id 翻译
    from ai_engine.agent import tool_router
    from ai_engine.persistence.db import init_db

    await init_db()
    received = await _register_fake("query_b_notxlate")

    def boom(name):
        raise AssertionError("B 端不应触发业务库 userCode 翻译")

    monkeypatch.setattr(tool_router, "get_db", boom)

    result = await tool_router.dispatch(
        tool_name="query_b_notxlate", params={}, user_type="b",
        subject_id="100000", conversation_id=1,
    )
    assert result["ok"] is True
    assert received["user_id"] == "100000"
