import pytest

pytestmark = pytest.mark.asyncio


async def _seed(audit):
    # conv1: query_kyc 空; conv1: query_transaction 非空; conv2: query_kyc 非空
    await audit.log_tool_call(1, "query_kyc", {}, 10, 1, False, None, result_count=0, is_empty=True, subject_id="a", user_type="c")
    await audit.log_tool_call(1, "query_transaction", {}, 10, 1, False, None, result_count=5, is_empty=False, subject_id="a", user_type="c")
    await audit.log_tool_call(2, "query_kyc", {}, 10, 1, False, None, result_count=3, is_empty=False, subject_id="b", user_type="c")


async def test_filter_by_tool(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit
    await init_db(); await _seed(audit)
    rows = await audit.recent_audits(limit=50, rejected_only=False, tool_name="query_kyc")
    assert {r["tool_name"] for r in rows} == {"query_kyc"} and len(rows) == 2


async def test_filter_empty_only(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit
    await init_db(); await _seed(audit)
    rows = await audit.recent_audits(limit=50, rejected_only=False, empty_only=True)
    assert all(r["is_empty"] in (1, True) for r in rows) and len(rows) == 1


async def test_filter_by_conversation(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit
    await init_db(); await _seed(audit)
    rows = await audit.recent_audits(limit=50, rejected_only=False, conversation_id=2)
    assert all(r["conversation_id"] == 2 for r in rows) and len(rows) == 1


async def test_cursor_pagination(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit
    await init_db(); await _seed(audit)
    page1 = await audit.recent_audits(limit=2, rejected_only=False)
    assert len(page1) == 2
    page2 = await audit.recent_audits(limit=2, rejected_only=False, before_id=page1[-1]["id"])
    assert all(r["id"] < page1[-1]["id"] for r in page2)
