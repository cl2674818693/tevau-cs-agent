import pytest

pytestmark = pytest.mark.asyncio


async def test_empty_result_logged_as_empty(temp_db_url, monkeypatch):
    from ai_engine.agent import tool_router
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db
    import ai_engine.persistence.audit as audit

    await init_db()

    async def h(user_id, **k):
        return {"kyc": None, "note": "无记录"}

    base.register(
        base.Tool(
            name="q_empty",
            description="x",
            input_schema={"type": "object", "properties": {}},
            handler=h,
            requires_subject_id=True,
            subject_field="user_id",
        )
    )
    await tool_router.dispatch(
        tool_name="q_empty",
        params={},
        user_type="c",
        subject_id="999",  # 纯数字跳过 userCode 翻译
        conversation_id=1,
    )
    rows = await audit.list_audits(1)
    last = rows[-1]
    assert last["is_empty"] in (1, True) and last["result_count"] == 0
    assert last["subject_id"] == "999" and last["user_type"] == "c"


async def test_nonempty_result_logged_with_count(temp_db_url, monkeypatch):
    from ai_engine.agent import tool_router
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db
    import ai_engine.persistence.audit as audit

    await init_db()

    async def h(user_id, **k):
        return {
            "card_transactions": [1, 2, 3],
            "card_count": 3,
            "wallet_flows": [],
            "wallet_count": 0,
        }

    base.register(
        base.Tool(
            name="q_full",
            description="x",
            input_schema={"type": "object", "properties": {}},
            handler=h,
            requires_subject_id=True,
            subject_field="user_id",
        )
    )
    await tool_router.dispatch(
        tool_name="q_full",
        params={},
        user_type="c",
        subject_id="999",
        conversation_id=2,
    )
    last = (await audit.list_audits(2))[-1]
    assert last["result_count"] == 3 and last["is_empty"] in (0, False)
