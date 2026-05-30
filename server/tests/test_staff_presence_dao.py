from ai_engine.persistence import staff_presence


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_heartbeat_insert_and_update(temp_db_url):
    await _init(temp_db_url)
    await staff_presence.heartbeat("AG1", "online")
    rows = await staff_presence.list_all()
    assert len(rows) == 1
    assert rows[0]["staff_id"] == "AG1"
    assert rows[0]["status"] == "online"
    await staff_presence.heartbeat("AG1", "away")
    rows2 = await staff_presence.list_all()
    assert len(rows2) == 1
    assert rows2[0]["status"] == "away"


async def test_set_offline(temp_db_url):
    await _init(temp_db_url)
    await staff_presence.heartbeat("AG1", "online")
    await staff_presence.set_offline("AG1")
    rows = await staff_presence.list_all()
    assert rows[0]["status"] == "offline"


async def test_list_active_with_window(temp_db_url):
    await _init(temp_db_url)
    from ai_engine.persistence import db
    await db.execute(
        "INSERT INTO staff_presence(staff_id, status, last_seen_at) "
        "VALUES ('OLD1', 'online', '2000-01-01 00:00:00')"
    )
    await staff_presence.heartbeat("FRESH1", "online")
    active = await staff_presence.list_active(window_seconds=300)
    ids = {r["staff_id"] for r in active}
    assert "FRESH1" in ids
    assert "OLD1" not in ids
