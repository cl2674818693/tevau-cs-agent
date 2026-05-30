from ai_engine.persistence import admin_sla


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_crud_policy(temp_db_url):
    await _init(temp_db_url)
    pid = await admin_sla.create_policy("take_time", 300, "all", None)
    rows = await admin_sla.list_policies()
    assert len(rows) == 1 and rows[0]["id"] == pid
    await admin_sla.set_policy_active(pid, 0)
    assert int((await admin_sla.list_policies())[0]["active"]) == 0


async def test_create_rejects_bad_metric(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await admin_sla.create_policy("bogus", 10, "all", None)


async def test_breaches_detects_untaken_conversation(temp_db_url):
    await _init(temp_db_url)
    from ai_engine.persistence import db
    # 一条很久以前创建、从未接管的会话
    await db.execute(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES ('c','u1','human_pending','2000-01-01 00:00:00')"
    )
    await admin_sla.create_policy("take_time", 60, "all", None)
    breaches = await admin_sla.compute_breaches()
    assert any(b["metric"] == "take_time" for b in breaches)
