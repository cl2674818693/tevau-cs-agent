from unittest.mock import AsyncMock, MagicMock


async def test_run_turn_failsoft_on_llm_exception(seeded_db, monkeypatch):
    """LLM 抛异常时：runtime 不裸抛，yield 兜底 error 事件，回合标 failed。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence import conversations as c

    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(ac, "_client", fake)

    evs = [
        ev
        async for ev in runtime.run_turn(
            conversation_id=1,
            user_type="b",
            subject_id="S1",
            user_message="q",
            client_message_id="cm-fail",
        )
    ]

    assert any(e.get("type") == "error" for e in evs)  # 兜底文案而非裸抛
    rows = await c.list_messages(1)
    turn = next(r for r in rows if r["role"] == "user" and r["client_message_id"] == "cm-fail")
    assert turn["status"] == "failed"
    assert turn["error_code"] == "INTERNAL_ERROR"


async def test_run_turn_success_marks_done(seeded_db, monkeypatch):
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence import conversations as c

    class FakeResp:
        def __init__(self):
            self.content = [MagicMock(type="text", text="ok 结论")]
            self.stop_reason = "end_turn"
            self.usage = MagicMock(input_tokens=5, output_tokens=5)

    calls = {"n": 0}

    async def fake_create(**kw):
        calls["n"] += 1
        return FakeResp()  # self-check 后第二轮也返回文本

    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=fake_create)
    monkeypatch.setattr(ac, "_client", fake)

    _ = [
        ev
        async for ev in runtime.run_turn(
            conversation_id=1,
            user_type="b",
            subject_id="S1",
            user_message="q",
            client_message_id="cm-ok",
        )
    ]
    turn = await c.find_completed_turn(1, "cm-ok")
    assert turn is not None  # status=done
