from ai_engine.persistence import agent_ratings


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_record_and_get(temp_db_url):
    await _init(temp_db_url)
    rid = await agent_ratings.record(
        conversation_id=1, staff_id="AG1", subject_id="u1",
        user_type="c", rating=5, comment="赞",
    )
    assert rid > 0
    row = await agent_ratings.get_for_conversation(conversation_id=1, subject_id="u1")
    assert row is not None and row["rating"] == 5


async def test_get_for_conversation_isolation(temp_db_url):
    """不同 subject_id 不能读到他人评分。"""
    await _init(temp_db_url)
    await agent_ratings.record(1, "AG1", "u1", "c", 5, None)
    row = await agent_ratings.get_for_conversation(conversation_id=1, subject_id="u_other")
    assert row is None


async def test_aggregate_by_staff(temp_db_url):
    await _init(temp_db_url)
    await agent_ratings.record(1, "AG1", "u1", "c", 5, None)
    await agent_ratings.record(2, "AG1", "u2", "c", 3, None)
    await agent_ratings.record(3, "AG2", "u3", "c", 4, None)
    agg = await agent_ratings.aggregate_by_staff("AG1")
    assert agg["count"] == 2
    assert agg["avg_rating"] == 4.0
