async def test_daily_token_usage_has_model_column(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, input_tokens, "
        "output_tokens, model) VALUES ('u1', 'b', '2026-05-30', 100, 50, 'claude-sonnet-4-6')"
    )
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id = 'u1'"
    )
    assert row is not None
    assert row["model"] == "claude-sonnet-4-6"


async def test_model_pricing_table_exists(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO model_pricing(model, input_price_per_1k_x10000, "
        "output_price_per_1k_x10000, currency, updated_at) "
        "VALUES ('claude-sonnet-4-6', 30000, 150000, 'USD', '2026-05-30 00:00:00')"
    )
    row = await db.fetch_one("SELECT * FROM model_pricing WHERE model='claude-sonnet-4-6'")
    assert row is not None and int(row["input_price_per_1k_x10000"]) == 30000
