"""Task 5.1: KPI 增 AI 质量指标 + 修接管比率口径。"""


async def test_ai_quality_handoff_and_downvote_rates(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import feedback as fb
    from ai_engine.persistence.staff_metrics import ai_quality

    # 4 个会话：2 个转人工 + 2 个普通 AI
    a = await c.create_conversation("c", "U1")
    await c.set_mode(a, "human_pending")
    b = await c.create_conversation("c", "U2")
    await c.set_mode(b, "human_takeover", "S1")
    await c.create_conversation("c", "U3")
    await c.create_conversation("c", "U4")

    # 反馈：2 down + 1 up -> downvote_rate = 2/3
    m1 = await c.append_message(a, "assistant", "x")
    await fb.add_feedback(a, m1, "down", "不准", "U1", "c")
    m2 = await c.append_message(b, "assistant", "y")
    await fb.add_feedback(b, m2, "down", "不准", "U2", "c")
    m3 = await c.append_message(a, "assistant", "z")
    await fb.add_feedback(a, m3, "up", None, "U1", "c")

    q = await ai_quality(None, None)

    assert q["total_conversations"] == 4
    assert q["handoff"] == 2
    assert abs(q["handoff_rate"] - 0.5) < 1e-9
    assert q["downvote"] == 2
    assert q["upvote"] == 1
    assert abs(q["downvote_rate"] - (2 / 3)) < 1e-9


async def test_ai_quality_tool_empty_rate_and_insights(seeded_db):
    from ai_engine.persistence import audit as audit_dao
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.staff_metrics import ai_quality

    cid = await c.create_conversation("c", "U1")
    # 4 次工具调用，1 次 is_empty
    await audit_dao.log_tool_call(cid, "query_user", {}, 0, 5, False, None, 0, True)
    await audit_dao.log_tool_call(cid, "query_user", {}, 10, 5, False, None, 2, False)
    await audit_dao.log_tool_call(cid, "query_card", {}, 5, 5, False, None, 1, False)
    await audit_dao.log_tool_call(cid, "query_card", {}, 5, 5, False, None, 1, None)

    # out_of_scope / failed_turns 走 insights 口径
    t1 = await c.append_user_turn(cid, "范围外", "k1")
    await c.set_turn_verdict(t1, "no")
    await c.finalize_turn(t1, "done")
    t2 = await c.append_user_turn(cid, "崩了", "k2")
    await c.finalize_turn(t2, "failed", "INTERNAL_ERROR")

    q = await ai_quality(None, None)

    assert q["tool_calls"] == 4
    assert q["tool_empty"] == 1
    assert abs(q["tool_empty_rate"] - 0.25) < 1e-9
    assert q["out_of_scope"] == 1
    assert q["failed_turns"] == 1


async def test_ai_quality_division_safe_when_empty(seeded_db):
    from ai_engine.persistence.staff_metrics import ai_quality

    q = await ai_quality(None, None)

    assert q["total_conversations"] == 0
    assert q["handoff_rate"] == 0.0
    assert q["downvote_rate"] == 0.0
    assert q["tool_empty_rate"] == 0.0


async def test_resolved_ratio_excludes_transfer_out_from_denominator(seeded_db):
    """take→transfer_out 的接管不应稀释 resolved_ratio/release_ratio 的分母。

    口径修正：分母只数被 release/resolved 收尾的接管（resolution-eligible），
    transfer_out 单列 transfer_ratio，分子分母口径一致。
    """
    from ai_engine.persistence.staff_metrics import compute_kpi, log_staff_action

    # 同一客服 S，4 次接管：1 resolved + 1 release + 2 transfer_out
    await log_staff_action(1, "S", "take")
    await log_staff_action(1, "S", "resolved")
    await log_staff_action(2, "S", "take")
    await log_staff_action(2, "S", "release")
    await log_staff_action(3, "S", "take")
    await log_staff_action(3, "S", "transfer_out")
    await log_staff_action(4, "S", "take")
    await log_staff_action(4, "S", "transfer_out")

    rows = await compute_kpi(None, None)
    row = next(r for r in rows if r["staff_id"] == "S")

    assert row["takeovers"] == 4
    assert row["resolved"] == 1
    assert row["releases"] == 1
    assert row["transfers"] == 2
    # 分母 = resolved + release = 2（剔除 transfer_out）
    assert abs(row["resolved_ratio"] - 0.5) < 1e-9
    assert abs(row["release_ratio"] - 0.5) < 1e-9
    # transfer_ratio 用 takeovers 作分母（转走占全部接管比例）
    assert abs(row["transfer_ratio"] - 0.5) < 1e-9
