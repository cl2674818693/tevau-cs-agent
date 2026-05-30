from ai_engine.persistence import admin_cost


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_upsert_and_list_pricing(temp_db_url):
    await _init(temp_db_url)
    await admin_cost.upsert_pricing("claude-sonnet-4-6", 30000, 150000, "USD")
    rows = await admin_cost.list_pricing()
    assert len(rows) == 1
    assert rows[0]["model"] == "claude-sonnet-4-6"
    assert int(rows[0]["input_price_per_1k_x10000"]) == 30000


async def test_usage_by_model_sums_correctly(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 1000, 500, 'claude-sonnet-4-6'), "
        "('u2', 'b', '2026-05-30', 2000, 700, 'claude-sonnet-4-6'), "
        "('u3', 'c', '2026-05-30', 100, 50, 'claude-haiku-4-5')"
    )
    rows = await admin_cost.usage_by_model(None, None)
    by = {r["model"]: r for r in rows}
    assert by["claude-sonnet-4-6"]["input_tokens"] == 3000
    assert by["claude-sonnet-4-6"]["output_tokens"] == 1200
    assert by["claude-haiku-4-5"]["input_tokens"] == 100


async def test_usage_by_model_with_pricing_computes_cost(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 10000, 5000, 'claude-sonnet-4-6')"
    )
    await admin_cost.upsert_pricing("claude-sonnet-4-6", 30000, 150000, "USD")
    rows = await admin_cost.usage_by_model(None, None, with_cost=True)
    row = next(r for r in rows if r["model"] == "claude-sonnet-4-6")
    # input cost = 10000 / 1000 * 30000 / 10000 = 30 USD
    # output cost = 5000 / 1000 * 150000 / 10000 = 75 USD
    assert row["input_cost"] == 30.0
    assert row["output_cost"] == 75.0
    assert row["total_cost"] == 105.0
    assert row["currency"] == "USD"
