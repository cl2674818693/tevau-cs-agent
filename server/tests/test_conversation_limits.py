from unittest.mock import AsyncMock, MagicMock


async def _seed_turns(conv_id: int, n: int) -> None:
    from ai_engine.persistence.conversations import append_message

    for i in range(n):
        await append_message(conv_id, role="user", content=f"问题 {i}")
        await append_message(conv_id, role="assistant", content=f"回答 {i}")


async def test_should_compact_on_turns(temp_db_url):
    from ai_engine.governance.conversation_limits import MAX_TURNS, should_compact
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation("b", "BU1")
    await _seed_turns(cid, MAX_TURNS - 1)
    assert await should_compact(cid) is False
    await _seed_turns(cid, 1)
    assert await should_compact(cid) is True


async def test_should_compact_on_tokens(temp_db_url):
    from ai_engine.governance.conversation_limits import MAX_INPUT_TOKENS, should_compact
    from ai_engine.persistence.conversations import append_message, create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation("b", "BU1")
    # 单条超大消息：字符数 > MAX_INPUT_TOKENS*4
    await append_message(cid, role="user", content="x" * (MAX_INPUT_TOKENS * 4 + 10))
    assert await should_compact(cid) is True


async def test_compact_creates_new_conv_and_archives(temp_db_url, monkeypatch):
    from ai_engine.agent import conversation_compactor as cc
    from ai_engine.persistence import db
    from ai_engine.persistence.conversations import (
        create_conversation,
        get_conversation,
        list_messages,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation("b", "BU1")
    await _seed_turns(cid, 3)

    fake = MagicMock()
    fake.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(type="text", text="摘要：用户问 card_bind 500，已建工单 AI-1。")]
        )
    )
    monkeypatch.setattr(cc._ac, "_client", fake)

    new_id = await cc.compact_conversation(cid)
    assert new_id != cid

    # 新会话第一条是 system 摘要
    new_msgs = await list_messages(new_id)
    assert new_msgs[0]["role"] == "system"
    assert "摘要" in str(new_msgs[0]["content"])

    # 同 subject、老会话归档
    new_conv = await get_conversation(new_id)
    assert new_conv is not None and new_conv["subject_id"] == "BU1"
    row = await db.fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
    assert row is not None and row["archived"] == 1


async def test_runtime_triggers_compaction(seeded_db, monkeypatch):
    """run_turn 入口检测到超长 → 推 system 事件 + 切到新会话。"""
    from ai_engine.agent import conversation_compactor as cc
    from ai_engine.agent import runtime
    from ai_engine.governance import conversation_limits as cl
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")

    monkeypatch.setattr(cl, "should_compact", AsyncMock(return_value=True))
    # 让 runtime import 的 should_compact 也指向 patch 后的
    monkeypatch.setattr(runtime, "should_compact", AsyncMock(return_value=True))

    fake = MagicMock()
    # 第一次调用：compactor 总结；之后：agent 回复（含 self-check）
    fake.messages.create = AsyncMock(
        side_effect=[
            MagicMock(content=[MagicMock(type="text", text="摘要：历史诊断 X。")]),
            MagicMock(
                content=[MagicMock(type="text", text="基于摘要继续。")], stop_reason="end_turn"
            ),
            MagicMock(
                content=[MagicMock(type="text", text="基于摘要继续。")], stop_reason="end_turn"
            ),
        ]
    )
    monkeypatch.setattr(ac, "_client", fake)
    monkeypatch.setattr(cc._ac, "_client", fake)

    events = []
    async for ev in runtime.run_turn(
        conversation_id=cid, user_type="b", subject_id="BU00243780", user_message="新问题"
    ):
        events.append(ev)

    assert any(e["type"] == "system" and "新对话" in e["text"] for e in events)
