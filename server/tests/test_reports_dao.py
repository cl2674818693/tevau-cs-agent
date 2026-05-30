from ai_engine.persistence import reports


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_definition_crud(temp_db_url):
    await _init(temp_db_url)
    rid = await reports.create_definition(
        name="按客服满意度",
        source="agent_ratings",
        dims=["staff_id"],
        filters=[],
        metrics=[{"op": "count", "col": "*", "alias": "n"},
                 {"op": "avg", "col": "rating", "alias": "avg_rating"}],
        owner="SUP1",
    )
    rows = await reports.list_definitions()
    assert any(r["id"] == rid for r in rows)


async def test_execute_simple_count_by_staff(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG1', 'u2', 'c', 4, '2026-06-01 01:00:00'), "
        "(3, 'AG2', 'u3', 'c', 3, '2026-06-01 02:00:00')"
    )
    result = await reports.execute(
        source="agent_ratings",
        dims=["staff_id"],
        filters=[],
        metrics=[{"op": "count", "col": "*", "alias": "n"},
                 {"op": "avg", "col": "rating", "alias": "avg_rating"}],
    )
    by = {row["staff_id"]: row for row in result["rows"]}
    assert by["AG1"]["n"] == 2
    assert by["AG2"]["n"] == 1


async def test_execute_with_filter(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG2', 'u2', 'c', 3, '2026-06-01 01:00:00')"
    )
    result = await reports.execute(
        source="agent_ratings",
        dims=["staff_id"],
        filters=[{"col": "rating", "op": ">=", "val": 4}],
        metrics=[{"op": "count", "col": "*", "alias": "n"}],
    )
    assert len(result["rows"]) == 1
    assert result["rows"][0]["staff_id"] == "AG1"


async def test_execute_rejects_unknown_source(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await reports.execute(
            source="evil_table",
            dims=[],
            filters=[],
            metrics=[{"op": "count", "col": "*", "alias": "n"}],
        )


async def test_execute_rejects_unknown_dim(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await reports.execute(
            source="agent_ratings",
            dims=["evil_column"],
            filters=[],
            metrics=[{"op": "count", "col": "*", "alias": "n"}],
        )
