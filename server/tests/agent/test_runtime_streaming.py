"""Agent runtime: 流式增量（text_delta + final）

被测对象：runtime._run_llm_streaming / runtime.run_turn 的流式行为。
mock 策略：
- 用 fake_stream 替换 _client.messages.stream，按用例造 final resp。
- monkeypatch token_budget.check_and_record 跳过 DB（不属于本文件范围）。
- seeded_db 提供自有库（conversations/messages 行需要落地）。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation, list_messages


async def _new_conv(user_type: str = "c", subject_id: str = "U001") -> int:
    return await create_conversation(user_type, subject_id)


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    """budget gate 默认放行；测试本身不验证记账。"""
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestRunLlmStreamingLowLevel:
    """_run_llm_streaming 单独跑：live=True 时按换行边界 yield text，最终 yield __final__。"""

    async def test_live_yields_text_and_final(self, monkeypatch, fake_stream, make_resp) -> None:
        resp = make_resp(text="hello\nworld")  # \n 触发即时 redact 输出一行
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(resp))

        events = [e async for e in rt._run_llm_streaming({"model": "m"}, live=True)]
        # 末尾必是 __final__；其余为 type=text 增量
        assert events[-1] == {"__final__": resp, "__streamed__": True}
        texts = [e["text"] for e in events if e.get("type") == "text"]
        assert "".join(texts) == "hello\nworld"

    async def test_live_no_trailing_newline_flushes_tail(
        self, monkeypatch, fake_stream, make_resp
    ) -> None:
        """无尾换行：text_delta 在 buf，flush 时一次性脱敏后 yield。"""
        resp = make_resp(text="abc")  # 不含 \n
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(resp))

        events = [e async for e in rt._run_llm_streaming({"model": "m"}, live=True)]
        text_events = [e for e in events if e.get("type") == "text"]
        assert text_events == [{"type": "text", "text": "abc"}]

    async def test_not_live_no_text_events(
        self, monkeypatch, fake_stream, make_resp
    ) -> None:
        """live=False（首轮/工具轮）只攒数据，不流出文本。"""
        resp = make_resp(text="should-not-leak")
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(resp))

        events = [e async for e in rt._run_llm_streaming({"model": "m"}, live=False)]
        text_events = [e for e in events if e.get("type") == "text"]
        assert text_events == []
        # __streamed__ 应为 False
        assert events[-1] == {"__final__": resp, "__streamed__": False}

    async def test_empty_text_no_events(
        self, monkeypatch, fake_stream, make_resp
    ) -> None:
        resp = make_resp(text="")
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(resp))

        events = [e async for e in rt._run_llm_streaming({"model": "m"}, live=True)]
        text_events = [e for e in events if e.get("type") == "text"]
        assert text_events == []


class TestRunTurnEndTurnSelfCheck:
    """end_turn → 第一轮缓冲不流出（self-check 修订），第二轮 live 流出最终文本。"""

    async def test_self_check_only_final_round_visible(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        # 第一轮 draft（缓冲，不出现在事件流），第二轮 final（live 流出）
        drafts = [make_resp(text="draft-text"), make_resp(text="final-text")]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(drafts))

        conv = await _new_conv()
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="hello",
            )
        ]
        texts = "".join(e["text"] for e in events if e.get("type") == "text")
        assert texts == "final-text"  # draft 文字不被流出
        # draft 轮不入库；只有 final 轮的 assistant 块落了一条
        msgs = await list_messages(conv)
        roles = [m["role"] for m in msgs]
        assert roles.count("assistant") == 1


class TestRunTurnNoSelfCheckPath:
    """无 self-check 路径：tool_use 轮 → end_turn 已自检的最终轮一次性吐文本。"""

    async def test_streamed_final_text_flows_once(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        # 第 1 轮 end_turn 仅一行文本，会进入 self-check；第 2 轮 self-check 后真正流出
        responses = [
            make_resp(text="hi"),
            make_resp(text="hi"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await _new_conv()
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="ping",
            )
        ]
        # 只有"最终（self-check 后）"那轮 live 流出
        texts = "".join(e["text"] for e in events if e.get("type") == "text")
        assert texts == "hi"


class TestRunTurnIncrementalChunks:
    """text 中含 \\n 时按行 yield，多行场景断言事件数和拼接结果。"""

    async def test_multi_line_text_emits_each_line(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        drafts = [
            make_resp(text="line1\nline2"),
            make_resp(text="line1\nline2\nline3"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(drafts))

        conv = await _new_conv()
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="give me lines",
            )
        ]
        text_events = [e for e in events if e.get("type") == "text"]
        # 第一轮缓冲不流；第二轮 3 段（2 个完整行 + tail）
        assert len(text_events) == 3
        assert "".join(e["text"] for e in text_events) == "line1\nline2\nline3"
