from ai_engine.persistence import staff_performance


async def _seed_one_takeover(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:00:00'), "
        "(1, 'AG1', 'resolved', '2026-05-30 00:05:00')"
    )


async def test_perf_basic_kpi(temp_db_url):
    await _seed_one_takeover(temp_db_url)
    p = await staff_performance.compute_performance("AG1", None, None)
    assert p["takeovers"] == 1
    assert p["resolved"] == 1
    assert p["avg_handle_seconds"] >= 0
    assert p["satisfaction"] == {"count": 0, "avg_rating": 0.0}
    assert p["qa"] == {"count": 0, "avg_score": 0.0}


async def test_perf_with_rating_and_qa(temp_db_url):
    from ai_engine.persistence import admin_qa, agent_ratings
    await _seed_one_takeover(temp_db_url)
    await agent_ratings.record(1, "AG1", "BU1", "b", 5, None)
    sid = await admin_qa.create_scorecard("c", [])
    await admin_qa.submit_review(1, "AG1", sid, 90, {})
    p = await staff_performance.compute_performance("AG1", None, None)
    assert p["satisfaction"]["count"] == 1 and p["satisfaction"]["avg_rating"] == 5.0
    assert p["qa"]["count"] == 1 and p["qa"]["avg_score"] == 90.0
