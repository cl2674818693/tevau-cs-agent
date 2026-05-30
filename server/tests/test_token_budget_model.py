async def test_record_persists_model(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    allowed, _ = await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    assert allowed is True
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage_by_model "
        "WHERE subject_id='BU1' AND user_type='b' AND model='claude-sonnet-4-6'"
    )
    assert row is not None
    assert row["model"] == "claude-sonnet-4-6"


async def test_record_without_model_uses_unknown_placeholder(temp_db_url):
    """M4: model None 时用 '(unknown)' 占位写入新表（旧表已删）。"""
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU2", 10, 5)
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage_by_model "
        "WHERE subject_id='BU2' AND user_type='b'"
    )
    assert row is not None
    assert row["model"] == "(unknown)"
