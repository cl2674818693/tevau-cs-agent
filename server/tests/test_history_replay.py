import json
from unittest.mock import AsyncMock, MagicMock


def _resp(text: str) -> MagicMock:
    return MagicMock(
        content=[MagicMock(type="text", text=text)],
        stop_reason="end_turn",
        usage=MagicMock(input_tokens=1, output_tokens=1),
    )


async def test_run_turn_replays_prior_history(seeded_db, monkeypatch):
    """run_turn 把已落库历史回放给模型，实现多轮上下文。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import append_message, create_conversation

    cid = await create_conversation("b", "BU00243780")
    await append_message(cid, "user", "我的卡 C1 为什么被锁")
    await append_message(
        cid, "assistant", json.dumps([{"type": "text", "text": "因为风控规则 R-1"}])
    )
    await append_message(cid, "human_agent", "我已帮你解锁")

    captured = {}
    fake = MagicMock()

    def _create(**kw):
        # messages 是 run_turn 内部 live 引用，快照首个调用避免后续 mutation 干扰
        captured.setdefault("messages", json.loads(json.dumps(kw["messages"])))
        return _resp("好的")

    fake.messages.create = AsyncMock(side_effect=lambda **kw: _create(**kw))
    monkeypatch.setattr(ac, "_client", fake)

    async for _ in runtime.run_turn(
        conversation_id=cid, user_type="b", subject_id="BU00243780", user_message="还有别的吗"
    ):
        pass

    msgs = captured["messages"]
    # 历史 + 当前消息都在
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "我的卡 C1 为什么被锁" in joined
    assert "风控规则 R-1" in joined
    assert "我已帮你解锁" in joined
    assert msgs[-1] == {"role": "user", "content": "还有别的吗"}
    # 第一条必须是 user（Anthropic 约束）
    assert msgs[0]["role"] == "user"


async def test_coalesce_adjacent_same_role():
    from ai_engine.agent.runtime import _coalesce

    out = _coalesce(
        [
            {"role": "user", "content": "a"},
            {"role": "user", "content": "b"},
            {"role": "assistant", "content": "c"},
        ]
    )
    assert out == [
        {"role": "user", "content": "a\nb"},
        {"role": "assistant", "content": "c"},
    ]


async def test_history_text_extracts_assistant_blocks():
    from ai_engine.agent.runtime import _history_text

    assert _history_text("assistant", json.dumps([{"type": "text", "text": "嗨"}])) == "嗨"
    assert _history_text("human_agent", "纯文本") == "纯文本"


async def test_fresh_conversation_has_no_history(seeded_db, monkeypatch):
    """新会话：仅当前消息，不回放（历史为空）。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    captured = {}
    fake = MagicMock()

    def _create(**kw):
        captured.setdefault("messages", json.loads(json.dumps(kw["messages"])))
        return _resp("hi")

    fake.messages.create = AsyncMock(side_effect=lambda **kw: _create(**kw))
    monkeypatch.setattr(ac, "_client", fake)

    async for _ in runtime.run_turn(
        conversation_id=cid, user_type="b", subject_id="BU00243780", user_message="第一句"
    ):
        pass
    assert captured["messages"] == [{"role": "user", "content": "第一句"}]
