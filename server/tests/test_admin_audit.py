from ai_engine.persistence import admin_audit


async def test_log_and_list(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await admin_audit.log_admin_action(
        actor="AD1", action="staff.create", target_type="staff",
        target_id="AG9", detail={"role": "agent"},
    )
    rows = await admin_audit.list_admin_actions(limit=10)
    assert len(rows) == 1
    assert rows[0]["actor"] == "AD1"
    assert rows[0]["action"] == "staff.create"
    assert rows[0]["target_id"] == "AG9"


async def test_list_filters_by_action(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await admin_audit.log_admin_action(actor="AD1", action="staff.create")
    await admin_audit.log_admin_action(actor="AD1", action="sla.update")
    rows = await admin_audit.list_admin_actions(action="sla.update", limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "sla.update"
