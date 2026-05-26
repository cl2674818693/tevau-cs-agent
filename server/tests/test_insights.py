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


async def test_knowledge_gaps_human_handoff(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import insights

    # 两个转人工会话 + 一个普通 ai 会话
    a = await c.create_conversation("c", "U1")
    await c.set_mode(a, "human_pending")
    b = await c.create_conversation("c", "U2")
    await c.set_mode(b, "human_takeover", "S1")
    d = await c.create_conversation("c", "U3")  # mode 默认 ai

    g = await insights.knowledge_gaps(None, None)
    assert g["human_handoff"] == 2
    # 原三项仍在
    assert "out_of_scope" in g and "failed_turns" in g and "thumbs_down" in g
    assert d  # 普通会话不计入


async def test_tool_health_aggregation(seeded_db):
    from ai_engine.persistence import audit as audit_dao
    from ai_engine.persistence import insights

    cid = 1
    # query_user: 3 calls, 1 empty, 1 rejected
    await audit_dao.log_tool_call(cid, "query_user", {}, 0, 5, False, None, 0, True)
    await audit_dao.log_tool_call(cid, "query_user", {}, 10, 5, False, None, 2, False)
    await audit_dao.log_tool_call(cid, "query_user", {}, 0, 5, True, "越权", 0, False)
    # query_card: 1 call, 0 empty (is_empty NULL 历史行), 0 rejected
    await audit_dao.log_tool_call(cid, "query_card", {}, 5, 5, False, None, 1, None)

    rows = await insights.tool_health(None, None)
    by = {r["tool_name"]: r for r in rows}

    qu = by["query_user"]
    assert qu["calls"] == 3
    assert qu["empty"] == 1
    assert qu["rejected"] == 1
    assert abs(qu["empty_rate"] - (1 / 3)) < 1e-9

    qc = by["query_card"]
    assert qc["calls"] == 1
    assert qc["empty"] == 0  # NULL 当作非空
    assert qc["rejected"] == 0
    assert qc["empty_rate"] == 0.0


async def test_gap_conversations_thumbs_down_and_failed(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import feedback as fb
    from ai_engine.persistence import insights

    # 差评会话
    conv_down = await c.create_conversation("c", "U1")
    mid = await c.append_message(conv_down, "assistant", "答复")
    await fb.add_feedback(conv_down, mid, "down", "不准", "U1", "c")
    # 失败回合会话
    conv_fail = await c.create_conversation("c", "U2")
    t = await c.append_user_turn(conv_fail, "崩了", "k1")
    await c.finalize_turn(t, "failed", "INTERNAL_ERROR")

    downs = await insights.gap_conversations("thumbs_down", None, None)
    assert conv_down in [r["conversation_id"] for r in downs]

    fails = await insights.gap_conversations("failed", None, None)
    assert conv_fail in [r["conversation_id"] for r in fails]


async def test_gap_conversations_invalid_kind(seeded_db):
    import pytest

    from ai_engine.persistence import insights

    with pytest.raises(ValueError):
        await insights.gap_conversations("drop_table", None, None)
