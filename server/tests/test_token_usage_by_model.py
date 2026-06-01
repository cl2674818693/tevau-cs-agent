async def test_record_double_writes_by_model_table(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    row = await db.fetch_one(
        "SELECT input_tokens, output_tokens FROM daily_token_usage_by_model "
        "WHERE subject_id='BU1' AND user_type='b' AND model='claude-sonnet-4-6'"
    )
    assert row is not None
    assert int(row["input_tokens"]) == 100
    assert int(row["output_tokens"]) == 50


async def test_same_subject_two_models_keep_separate(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU2", 1000, 500, model="claude-sonnet-4-6")
    await check_and_record("b", "BU2", 200, 100, model="claude-haiku-4-5")
    rows = await db.fetch_all(
        "SELECT model, input_tokens, output_tokens FROM daily_token_usage_by_model "
        "WHERE subject_id='BU2' AND user_type='b' ORDER BY model"
    )
    by = {r["model"]: r for r in rows}
    assert int(by["claude-sonnet-4-6"]["input_tokens"]) == 1000
    assert int(by["claude-haiku-4-5"]["input_tokens"]) == 200
