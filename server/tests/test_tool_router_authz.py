async def test_router_injects_subject_id_for_subject_required_tool(monkeypatch, temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db

    await init_db()  # dispatch 总会 log_tool_call，需要审计表

    async def fake_handler(subject_id: str):
        return {"subject_id": subject_id}

    base.register(
        base.Tool(
            name="query_bu_fake",
            description="fake",
            input_schema={"type": "object", "properties": {}},
            handler=fake_handler,
            requires_subject_id=True,  # subject_field 默认 "subject_id"
        )
    )

    # AI 试图传 subject_id=OTHER，router 应强制覆盖为会话身份
    result = await dispatch(
        tool_name="query_bu_fake",
        params={"subject_id": "OTHER"},
        user_type="b",
        subject_id="100000",
        conversation_id=1,
    )
    assert result["ok"] is True
    assert result["data"]["subject_id"] == "100000"


async def test_router_rejects_unknown_tool(monkeypatch, temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.persistence.db import init_db

    await init_db()  # 未知工具也会 log_tool_call，需要审计表

    out = await dispatch(
        tool_name="nope", params={}, user_type="b", subject_id="BU1", conversation_id=1
    )
    assert out["ok"] is False
    assert "unknown" in out["error"]


async def test_router_audits_call(monkeypatch, temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base
    from ai_engine.persistence.audit import list_audits
    from ai_engine.persistence.db import init_db

    async def fake_ok(x: str):
        return {"echo": x}

    base.register(
        base.Tool(
            name="echo_tool",
            description="",
            input_schema={"type": "object"},
            handler=fake_ok,
            requires_subject_id=False,
        )
    )

    await init_db()
    await dispatch(
        tool_name="echo_tool",
        params={"x": "hi"},
        user_type="b",
        subject_id="BU1",
        conversation_id=1,
    )
    rows = await list_audits(conversation_id=1)
    assert rows and rows[0]["tool_name"] == "echo_tool"
