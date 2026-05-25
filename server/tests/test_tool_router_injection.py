"""A4: prompt 注入 / 越权对抗回归测试。

核心安全不变量（结构性防护，不依赖模型听话）：
1. AI 在 params 里塞别人的 subject_id —— router 强制覆盖为会话身份（已由
   test_tool_router_authz 覆盖，这里补 unmask 维度）。
2. AI 在 params 里自塞 unmask=True 试图解除脱敏 —— router 只认调用方显式 unmask
   且工具声明 supports_unmask，AI 自塞的一律 pop 掉。
"""

import pytest

pytestmark = pytest.mark.asyncio


async def test_ai_cannot_self_grant_unmask_on_unsupported_tool(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db

    await init_db()

    received = {}

    async def fake_handler(subject_id: str, **kwargs):
        received.update(kwargs)
        return {"subject_id": subject_id, "kwargs": kwargs}

    base.register(
        base.Tool(
            name="query_no_unmask",
            description="fake",
            input_schema={"type": "object", "properties": {}},
            handler=fake_handler,
            requires_subject_id=True,
            supports_unmask=False,
        )
    )

    # AI 注入 unmask=True，但工具不支持 unmask 且 dispatch 未传 unmask
    result = await dispatch(
        tool_name="query_no_unmask",
        params={"subject_id": "OTHER", "unmask": True},
        user_type="b",
        subject_id="100000",
        conversation_id=1,
    )
    assert result["ok"] is True
    assert result["data"]["subject_id"] == "100000"  # 身份被强制覆盖
    assert "unmask" not in received  # AI 自塞的 unmask 被 pop，未泄露给 handler


async def test_ai_cannot_self_grant_unmask_when_caller_did_not(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db

    await init_db()

    received = {}

    async def fake_handler(subject_id: str, unmask: bool = False):
        received["unmask"] = unmask
        return {"unmask": unmask}

    base.register(
        base.Tool(
            name="query_unmaskable",
            description="fake",
            input_schema={"type": "object", "properties": {}},
            handler=fake_handler,
            requires_subject_id=True,
            supports_unmask=True,
        )
    )

    # 工具支持 unmask，但调用方（engineer 代查链路）没传 unmask=True；
    # AI 在 params 里自塞 unmask=True 不应生效
    result = await dispatch(
        tool_name="query_unmaskable",
        params={"unmask": True},
        user_type="b",
        subject_id="100000",
        conversation_id=1,
        unmask=False,
    )
    assert result["ok"] is True
    assert received["unmask"] is False  # 仍是脱敏态
