async def test_turn_processing_then_done(seeded_db):
    from ai_engine.persistence import conversations as c

    tid = await c.append_user_turn(1, "hi", "cmid-1")
    rows = await c.list_messages(1)
    assert any(r["id"] == tid and r["status"] == "processing" for r in rows)
    await c.finalize_turn(tid, "done")
    assert await c.find_completed_turn(1, "cmid-1") is not None


async def test_find_completed_turn_ignores_processing(seeded_db):
    from ai_engine.persistence import conversations as c

    await c.append_user_turn(1, "hi", "cmid-2")  # 留在 processing
    assert await c.find_completed_turn(1, "cmid-2") is None


async def test_turn_verdict_and_assistant_texts(seeded_db):
    from ai_engine.persistence import conversations as c

    tid = await c.append_user_turn(1, "q", "cmid-3")
    await c.set_turn_verdict(tid, "no")
    await c.append_message(1, "assistant", "答复A")
    await c.append_message(1, "assistant", "答复B")
    txts = await c.get_turn_assistant_texts(1, tid)
    assert txts == ["答复A", "答复B"]
    rows = await c.list_messages(1)
    assert any(r["id"] == tid and r["topic_verdict"] == "no" for r in rows)


async def test_assistant_message_persists_prompt_version(seeded_db):
    """灰度 A/B 闭环：写 assistant 消息时落 prompt_version，便于按版本对比效果。"""
    from ai_engine.persistence import conversations as c

    mid = await c.append_message(1, "assistant", "答复", prompt_version="v1.1.0")
    rows = await c.list_messages(1)
    row = next(r for r in rows if r["id"] == mid)
    assert row["prompt_version"] == "v1.1.0"
