"""Task 2.1: 会话列表暴露风险信号 + risk_only 筛选。

风险信号（库里已有）：
- messages.status='failed'（回合失败）
- messages.topic_verdict='no'（范围外）
- message_feedback.rating='down'（差评）
- tool_audits.is_empty=1（工具空结果）
- conversations.needs_review=1（待复核）

关键点：mode='ai' 但有风险的会话（AI 答错没转人工）必须能被 risk_only=True 选出。
"""


async def test_risk_only_surfaces_ai_conversation_with_failed_turn(temp_db_url):
    from ai_engine.persistence.conversations import (
        append_user_turn,
        create_conversation,
        finalize_turn,
        list_for_staff,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    # mode='ai'（默认），但有一条失败回合 → 不在普通列表，但应被 risk_only 选出
    cid = await create_conversation(user_type="c", subject_id="U1")
    turn = await append_user_turn(cid, content="出问题了", client_message_id=None)
    await finalize_turn(turn, status="failed", error_code="INTERNAL_ERROR")

    # 普通 all 列表只看非 ai，不含本会话
    normal = await list_for_staff("all")
    assert cid not in [c["id"] for c in normal]

    # risk_only=True 应选出该 ai 会话
    risky = await list_for_staff(risk_only=True)
    ids = [c["id"] for c in risky]
    assert cid in ids
    row = next(c for c in risky if c["id"] == cid)
    assert int(row["has_failed"]) == 1


async def test_risk_signals_downvote_and_needs_review(temp_db_url):
    from ai_engine.persistence.conversations import (
        create_conversation,
        list_for_staff,
        mark_needs_review,
    )
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.feedback import add_feedback

    await init_db()
    c_down = await create_conversation(user_type="c", subject_id="U2")
    await add_feedback(c_down, message_id=1, rating="down", reason="答非所问",
                       subject_id="U2", user_type="c")

    c_review = await create_conversation(user_type="c", subject_id="U3")
    await mark_needs_review(c_review)

    risky = await list_for_staff(risk_only=True)
    by_id = {c["id"]: c for c in risky}
    assert c_down in by_id
    assert int(by_id[c_down]["has_downvote"]) == 1
    assert c_review in by_id
    assert int(by_id[c_review]["needs_review"]) == 1


async def test_risk_signals_out_of_scope_and_empty_tool(temp_db_url):
    from ai_engine.persistence.audit import log_tool_call
    from ai_engine.persistence.conversations import (
        append_user_turn,
        create_conversation,
        list_for_staff,
        set_turn_verdict,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    c_oos = await create_conversation(user_type="c", subject_id="U4")
    turn = await append_user_turn(c_oos, content="无关问题", client_message_id=None)
    await set_turn_verdict(turn, "no")

    c_empty = await create_conversation(user_type="c", subject_id="U5")
    await log_tool_call(
        conversation_id=c_empty, tool_name="query_user", params={}, result_size=0,
        duration_ms=1, rejected=False, reject_reason=None, result_count=0, is_empty=True,
    )

    risky = await list_for_staff(risk_only=True)
    by_id = {c["id"]: c for c in risky}
    assert c_oos in by_id
    assert int(by_id[c_oos]["has_out_of_scope"]) == 1
    assert c_empty in by_id
    assert int(by_id[c_empty]["has_empty_tool"]) == 1


async def test_risk_only_excludes_clean_conversation(temp_db_url):
    from ai_engine.persistence.conversations import (
        append_user_turn,
        create_conversation,
        finalize_turn,
        list_for_staff,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="c", subject_id="CLEAN")
    turn = await append_user_turn(cid, content="正常问题", client_message_id=None)
    await finalize_turn(turn, status="done")

    risky = await list_for_staff(risk_only=True)
    assert cid not in [c["id"] for c in risky]


async def test_get_meta_with_risk_returns_signals(temp_db_url):
    """详情页右侧信息卡：单会话拿到与列表页同口径的风险信号。"""
    from ai_engine.persistence.conversations import (
        append_user_turn,
        create_conversation,
        finalize_turn,
        get_meta_with_risk,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="c", subject_id="U1")
    turn = await append_user_turn(cid, content="出问题了", client_message_id=None)
    await finalize_turn(turn, status="failed", error_code="X")

    row = await get_meta_with_risk(cid)
    assert row is not None
    assert row["id"] == cid
    assert row["user_type"] == "c"
    assert row["subject_id"] == "U1"
    assert int(row["has_failed"]) == 1
    assert int(row["has_downvote"]) == 0
    assert int(row["needs_review"]) == 0


async def test_get_meta_with_risk_not_found(temp_db_url):
    from ai_engine.persistence.conversations import get_meta_with_risk
    from ai_engine.persistence.db import init_db

    await init_db()
    assert await get_meta_with_risk(999999) is None


async def test_default_mode_filter_unchanged_regression(temp_db_url):
    """risk_only=False（默认）时，原有 mode 过滤行为不变。"""
    from ai_engine.persistence.conversations import (
        append_human_message,
        create_conversation,
        list_for_staff,
        set_mode,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    c1 = await create_conversation(user_type="c", subject_id="U1")
    await create_conversation(user_type="c", subject_id="U2")  # stays ai
    await set_mode(c1, "human_pending")
    await append_human_message(c1, sender_staff_id="S100", content="您好")

    pending = await list_for_staff("human_pending")
    assert [c["id"] for c in pending] == [c1]
    assert await list_for_staff("all")
