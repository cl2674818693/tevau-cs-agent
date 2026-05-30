from ai_engine.persistence import db, shifts_query


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_is_on_shift_true_when_in_window(temp_db_url):
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO staff_shifts(staff_id, start_at, end_at, created_at) "
        "VALUES ('AG1', '2026-06-01 09:00:00', '2026-06-01 18:00:00', '2026-06-01 00:00:00')"
    )
    assert await shifts_query.is_on_shift("AG1", "2026-06-01 12:00:00") is True


async def test_is_on_shift_false_outside_window(temp_db_url):
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO staff_shifts(staff_id, start_at, end_at, created_at) "
        "VALUES ('AG1', '2026-06-01 09:00:00', '2026-06-01 18:00:00', '2026-06-01 00:00:00')"
    )
    assert await shifts_query.is_on_shift("AG1", "2026-06-02 12:00:00") is False
