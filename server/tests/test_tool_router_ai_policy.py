"""AI 自动调用受 tool_policies(role=ai) 控制：默认放行，DB 显式禁用即拒。"""

import pytest


async def test_ai_default_allowed(temp_db_url):
    """表空时不阻塞（具体业务可能因数据源缺失返回 error，但不应是 PermissionError）。"""
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    try:
        await dispatch(
            tool_name="lookup_error_code", params={"code": "E1"},
            user_type="c", subject_id="u1", conversation_id=1,
        )
    except PermissionError:
        pytest.fail("default should not block AI calls")
    except Exception:
        pass


async def test_ai_blocked_when_db_denies(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "lookup_error_code", "role": "ai",
         "allowed": 0, "unmask_allowed": 0},
    ])
    with pytest.raises(PermissionError):
        await dispatch(
            tool_name="lookup_error_code", params={"code": "E1"},
            user_type="c", subject_id="u1", conversation_id=1,
        )
