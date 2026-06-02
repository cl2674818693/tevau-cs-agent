"""Agent runtime: LLM 输出 PII 兜底脱敏

被测对象：runtime._StreamRedactor 行内/流式脱敏 + _final_text_events 一次性兜底脱敏。
mock 策略：用 fake_stream 造出包含 PII 的 LLM 文本，断言流出的 text 已被替换。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestStreamRedactorLine:
    """_StreamRedactor 按换行边界批量脱敏；行内 PII 不应跨增量漏脱。"""

    def test_phone_in_complete_line(self) -> None:
        r = rt._StreamRedactor()
        out = r.feed("用户手机 13812345678 已绑定\n")
        assert out == ["用户手机 138****78 已绑定\n"]
        assert r.flush() == ""

    def test_id_card_in_complete_line(self) -> None:
        r = rt._StreamRedactor()
        out = r.feed("证件 11010119900307123X 已通过\n")
        assert out and "11010119900307123X" not in out[0]
        assert "11" in out[0]  # 前 2 位保留

    def test_email_in_complete_line(self) -> None:
        r = rt._StreamRedactor()
        out = r.feed("邮箱 alice@example.com 已确认\n")
        assert out and "alice@example.com" not in out[0]
        assert "al***@example.com" in out[0]

    def test_card_number_in_complete_line(self) -> None:
        r = rt._StreamRedactor()
        out = r.feed("卡号 4938 7506 7246 4590 风险\n")
        assert out and "4938 7506 7246 4590" not in out[0]

    def test_rule_name_redacted(self) -> None:
        r = rt._StreamRedactor()
        out = r.feed("命中 R-217 拦截\n")
        assert "R-217" not in out[0]
        assert "[风控规则]" in out[0]

    def test_buffer_holds_partial_line(self) -> None:
        """没有换行的 chunk 暂存在 buf，下个 \\n 触发整段脱敏。"""
        r = rt._StreamRedactor()
        out1 = r.feed("phone=1381234")
        assert out1 == []  # 没换行不出
        out2 = r.feed("5678 done\n")
        # 拼接后 13812345678 被识别脱敏
        joined = "".join(out2)
        assert "13812345678" not in joined
        assert "138****78" in joined

    def test_flush_redacts_tail(self) -> None:
        r = rt._StreamRedactor()
        assert r.feed("片段 alice@x.com") == []
        assert "alice@x.com" not in r.flush()

    def test_empty_input(self) -> None:
        r = rt._StreamRedactor()
        assert r.feed("") == []
        assert r.flush() == ""


class TestRuntimeRedactionEndToEnd:
    """run_turn 实际流出的文本应已脱敏。"""

    async def test_runtime_redacts_phone_in_final_text(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        # 第一轮 draft（不流），第二轮 self-check 后 live 流出
        responses = [
            make_resp(text="我帮你查 13812345678 的状态\n"),
            make_resp(text="您的手机号 13812345678 状态正常\n"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="查一下",
            )
        ]
        text = "".join(e["text"] for e in events if e.get("type") == "text")
        assert "13812345678" not in text
        assert "138****78" in text


class TestFinalTextEventsHelper:
    """_final_text_events：streamed=True 不再补发；False 时所有 texts 兜底脱敏后一次性出。"""

    def test_streamed_true_returns_empty(self) -> None:
        assert rt._final_text_events(True, ["whatever 13812345678"]) == []

    def test_streamed_false_emits_all_redacted(self) -> None:
        evs = rt._final_text_events(False, ["你好 13812345678 \n再见 a@b.com"])
        assert len(evs) == 1
        assert "13812345678" not in evs[0]["text"]
        assert "a@b.com" not in evs[0]["text"]

    def test_streamed_false_multi_text_blocks(self) -> None:
        evs = rt._final_text_events(False, ["a R-12", "b 13812345678"])
        assert len(evs) == 2
        assert "[风控规则]" in evs[0]["text"]
        assert "13812345678" not in evs[1]["text"]
