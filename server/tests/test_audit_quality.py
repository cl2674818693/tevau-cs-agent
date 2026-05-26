import pytest

pytestmark = pytest.mark.asyncio


async def test_log_tool_call_persists_quality_fields(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit

    await init_db()
    await audit.log_tool_call(
        conversation_id=1, tool_name="query_kyc", params={"user_id": "212433"},
        result_size=20, duration_ms=5, rejected=False, reject_reason=None,
        result_count=0, is_empty=True, subject_id="212433", user_type="c",
    )
    rows = await audit.list_audits(1)
    assert rows[0]["result_count"] == 0 and rows[0]["is_empty"] in (1, True)
    assert rows[0]["subject_id"] == "212433" and rows[0]["user_type"] == "c"
