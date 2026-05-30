from ai_engine.persistence import admin_shifts


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_and_list(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    rows = await admin_shifts.list_shifts(staff_id="AG1")
    assert len(rows) == 1 and rows[0]["id"] == sid


async def test_filter_by_time_range(temp_db_url):
    await _init(temp_db_url)
    await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    await admin_shifts.create_shift("AG1", "2026-06-02 09:00:00", "2026-06-02 18:00:00")
    rows = await admin_shifts.list_shifts(
        staff_id="AG1", date_from="2026-06-02 00:00:00"
    )
    assert len(rows) == 1


async def test_delete_shift(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    await admin_shifts.delete_shift(sid)
    rows = await admin_shifts.list_shifts(staff_id="AG1")
    assert len(rows) == 0
