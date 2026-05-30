"""AI 自动调用的 unmask 决策（dispatch 未显式传 unmask）：

- 表空/无 DB 记录：fallback 默认 False（role=ai 不在 engineer 白名单）
- DB 显式开启：unmask=True（DB 优先）

dispatch 路径：调用方不传 unmask kwarg → dispatch 内查 is_unmask_allowed("ai", tool)
→ 通过 safe_params['unmask'] 透传到工具。
"""


async def test_ai_default_unmask_false_when_db_empty(temp_db_url):
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db

    await init_db()
    tool_policies.invalidate_cache()
    assert await tool_policies.is_unmask_allowed("query_user", "ai") is False


async def test_ai_unmask_true_when_db_says_so(temp_db_url):
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db

    await init_db()
    tool_policies.invalidate_cache()
    await tool_policies.upsert_many(
        "AD1",
        [
            {
                "tool_name": "query_user",
                "role": "ai",
                "allowed": 1,
                "unmask_allowed": 1,
            }
        ],
    )
    assert await tool_policies.is_unmask_allowed("query_user", "ai") is True


async def test_dispatch_reads_unmask_from_db_when_not_passed(temp_db_url, monkeypatch):
    """dispatch 未传 unmask kwarg 时，从 is_unmask_allowed('ai', tool) 取值，落到 safe_params。"""
    from ai_engine.agent import tool_router
    from ai_engine.agent.tools import base
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db

    await init_db()
    tool_policies.invalidate_cache()

    # DB 显式开 unmask
    await tool_policies.upsert_many(
        "AD1",
        [
            {
                "tool_name": "_test_unmask",
                "role": "ai",
                "allowed": 1,
                "unmask_allowed": 1,
            }
        ],
    )

    captured: dict = {}

    async def fake_handler(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    fake_tool = base.Tool(
        name="_test_unmask",
        description="test",
        input_schema={"type": "object"},
        handler=fake_handler,
        supports_unmask=True,
    )
    monkeypatch.setitem(base.REGISTRY, "_test_unmask", fake_tool)

    # 不传 unmask（即默认 None）→ 应自动注入 True
    await tool_router.dispatch(
        tool_name="_test_unmask",
        params={},
        user_type="b",
        subject_id="BU1",
        conversation_id=1,
    )
    assert captured.get("unmask") is True

    tool_policies.invalidate_cache()
