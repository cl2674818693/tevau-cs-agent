from ai_engine.persistence import db, reports


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_count_if_metric(temp_db_url):
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO message_feedback(conversation_id, message_id, rating, "
        "subject_id, user_type, created_at) VALUES "
        "(1, 1, 'up', 'u1', 'c', '2026-06-01 00:00:00'), "
        "(2, 1, 'up', 'u1', 'c', '2026-06-01 00:00:00'), "
        "(3, 1, 'down', 'u1', 'c', '2026-06-01 00:00:00')"
    )
    result = await reports.execute(
        source="message_feedback",
        dims=["user_type"],
        filters=[],
        metrics=[
            {"op": "count", "col": "*", "alias": "n"},
            {"op": "count_if", "col": "rating", "match": "up", "alias": "n_up"},
        ],
    )
    row = next(r for r in result["rows"] if r["user_type"] == "c")
    assert row["n"] == 3
    assert row["n_up"] == 2


async def test_count_if_requires_match(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await reports.execute(
            source="message_feedback",
            dims=["user_type"],
            filters=[],
            metrics=[{"op": "count_if", "col": "rating", "alias": "n"}],
        )
