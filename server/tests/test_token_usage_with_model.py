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
