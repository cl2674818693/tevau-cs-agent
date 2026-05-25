async def test_reclaim_marks_old_processing_failed(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import db
    from ai_engine.persistence.maintenance import reclaim_stale_turns

    tid = await c.append_user_turn(1, "卡住的", "stale-1")
    # 手动把 created_at 改成很久以前，模拟僵尸回合
    await db.execute(
        "UPDATE messages SET created_at='2000-01-01 00:00:00' WHERE id=:id", {"id": tid}
    )
    n = await reclaim_stale_turns(120)
    assert n == 1
    rows = await c.list_messages(1)
    turn = next(r for r in rows if r["id"] == tid)
    assert turn["status"] == "failed"
    assert turn["error_code"] == "STALE_RECLAIMED"


async def test_reclaim_keeps_recent_processing(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.maintenance import reclaim_stale_turns

    tid = await c.append_user_turn(1, "刚发的", "fresh-1")
    assert await reclaim_stale_turns(120) == 0
    rows = await c.list_messages(1)
    assert next(r for r in rows if r["id"] == tid)["status"] == "processing"


async def test_sweep_loop_disabled_returns_immediately(monkeypatch):
    monkeypatch.setenv("STALE_SWEEP_INTERVAL_SECONDS", "0")
    from ai_engine.config import settings
    from ai_engine.persistence.maintenance import sweep_loop

    settings.reload()
    await sweep_loop()  # 不应卡住
    settings.reload()
