async def test_record_persists_model(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    allowed, _ = await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    assert allowed is True
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id='BU1' AND user_type='b'"
    )
    assert row is not None
    assert row["model"] == "claude-sonnet-4-6"


async def test_record_without_model_keeps_null(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU2", 10, 5)
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id='BU2' AND user_type='b'"
    )
    assert row is not None
    assert row["model"] is None
