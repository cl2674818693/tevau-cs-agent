from unittest.mock import AsyncMock, MagicMock


async def test_runtime_redacts_pii_in_streamed_text(seeded_db, monkeypatch):
    """LLM 返回含手机/卡号/规则名的文本 → runtime yield 出来的是脱敏版。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac

    leaky = "您的手机 13812345678 卡号 4938750672464590 触发规则 R-217"

    class FakeResp:
        def __init__(self):
            self.content = [MagicMock(type="text", text=leaky)]
            self.stop_reason = "end_turn"
            self.usage = MagicMock(input_tokens=1, output_tokens=1)

    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=FakeResp())
    monkeypatch.setattr(ac, "_client", fake_client)

    texts = []
    async for ev in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="BU00243780", user_message="hi"
    ):
        if ev["type"] == "text":
            texts.append(ev["text"])

    joined = "".join(texts)
    assert "13812345678" not in joined
    assert "4938750672464590" not in joined
    assert "R-217" not in joined
    assert "[风控规则]" in joined
