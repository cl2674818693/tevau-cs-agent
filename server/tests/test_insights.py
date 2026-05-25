async def test_knowledge_gaps_counts(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import feedback as fb
    from ai_engine.persistence import insights

    t1 = await c.append_user_turn(1, "范围外", "k1")
    await c.set_turn_verdict(t1, "no")
    await c.finalize_turn(t1, "done")
    t2 = await c.append_user_turn(1, "崩了", "k2")
    await c.finalize_turn(t2, "failed", "INTERNAL_ERROR")
    mid = await c.append_message(1, "assistant", "x")
    await fb.add_feedback(1, mid, "down", "不准", "BU00243780", "b")

    g = await insights.knowledge_gaps(None, None)
    assert g["out_of_scope"] == 1
    assert g["failed_turns"] == 1
    assert g["thumbs_down"] == 1
