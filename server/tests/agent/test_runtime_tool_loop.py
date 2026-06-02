"""Agent runtime: 多轮工具调用循环

被测对象：runtime._agent_loop 在多轮 tool_use → tool_result 闭环中的行为。
- 顺序：tool_call 事件先于 tool_result 事件。
- 工具调用 fan-out（一轮多个 tool_use）的执行顺序与结果聚合。
- 中间文本（工具轮的 text）即时流出。
- 最终轮经过 self-check 才落库 + 流给用户。

mock 策略：
- 注入临时工具 echo_tool / count_tool，handler 返回可断言结构。
- _client.messages.stream 用 fake_stream 多轮回放。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.agent.tools import base as toolbase
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation, list_messages


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


@pytest.fixture
def _register_echo(monkeypatch):
    """注册临时 echo_tool：返回 {ok:[args]}。yield 完移除注册。"""
    calls: list[dict] = []

    async def _h(**kw):  # noqa: ANN003
        calls.append(kw)
        return {"echoed": kw, "count": 1}

    toolbase.register(
        toolbase.Tool(
            name="echo_tool",
            description="echo",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=_h,
        )
    )
    yield calls
    toolbase.REGISTRY.pop("echo_tool", None)


class TestSingleToolRound:
    """1 次工具调用 → 1 个 tool_call 事件 + 1 个 tool_result 事件，顺序固定。"""

    async def test_tool_call_then_result_then_text(
        self, monkeypatch, seeded_db, fake_stream, make_resp, _register_echo
    ) -> None:
        # 1: tool_use（echo_tool）; 2: end_turn 出文本（self-check 前 draft）; 3: self-check 后 final
        responses = [
            make_resp(
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "echo_tool", "input": {"x": "hi"}}],
            ),
            make_resp(text="draft"),
            make_resp(text="完成"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="ping",
            )
        ]
        types = [e.get("type") for e in events]
        # tool_call 必先于 tool_result
        assert types.index("tool_call") < types.index("tool_result")
        # echo handler 被调到
        assert _register_echo and _register_echo[0]["x"] == "hi"


class TestToolFanOut:
    """同一轮多个 tool_use：按声明顺序执行；每个都产出独立 tool_call + tool_result 事件。"""

    async def test_two_tools_in_one_round(
        self, monkeypatch, seeded_db, fake_stream, make_resp, _register_echo
    ) -> None:
        responses = [
            make_resp(
                stop_reason="tool_use",
                tool_calls=[
                    {"id": "t1", "name": "echo_tool", "input": {"x": "a"}},
                    {"id": "t2", "name": "echo_tool", "input": {"x": "b"}},
                ],
            ),
            make_resp(text="draft"),
            make_resp(text="done"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))
        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="go",
            )
        ]
        tool_calls = [e for e in events if e.get("type") == "tool_call"]
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        assert [e["id"] for e in tool_calls] == ["t1", "t2"]
        assert [e["id"] for e in tool_results] == ["t1", "t2"]
        # 两次 handler 调用
        assert [c["x"] for c in _register_echo] == ["a", "b"]


class TestMultiRoundToolLoop:
    """2 轮工具调用：第一轮 echo_tool，第二轮再 echo_tool，最后 end_turn 出文本。"""

    async def test_two_tool_rounds_then_text(
        self, monkeypatch, seeded_db, fake_stream, make_resp, _register_echo
    ) -> None:
        responses = [
            make_resp(
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "echo_tool", "input": {"x": "1"}}],
            ),
            make_resp(
                stop_reason="tool_use",
                tool_calls=[{"id": "t2", "name": "echo_tool", "input": {"x": "2"}}],
            ),
            make_resp(text="draft"),
            make_resp(text="finally"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))
        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="go",
            )
        ]
        tool_ids = [e["id"] for e in events if e.get("type") == "tool_call"]
        assert tool_ids == ["t1", "t2"]
        text = "".join(e["text"] for e in events if e.get("type") == "text")
        assert "finally" in text


class TestToolResultLargePayloadTruncated:
    """工具返回超大 payload：guard.maybe_truncate 截断，is_error=False（成功但截断）。"""

    async def test_large_payload_truncated(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        async def _big(**_kw):  # noqa: ANN003
            return {"items": ["x" * 1000 for _ in range(500)]}  # 50万字节级

        toolbase.register(
            toolbase.Tool(
                name="big_tool",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_big,
            )
        )
        # 缩小 max_tool_result_bytes 让截断必发生
        from ai_engine.config import settings as _settings

        monkeypatch.setattr(_settings, "max_tool_result_bytes", 1024)

        responses = [
            make_resp(
                stop_reason="tool_use",
                tool_calls=[{"id": "tb", "name": "big_tool", "input": {}}],
            ),
            make_resp(text="draft"),
            make_resp(text="done"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))
        try:
            conv = await create_conversation("c", "U001")
            events = [
                e
                async for e in rt.run_turn(
                    conversation_id=conv,
                    user_type="c",
                    subject_id="U001",
                    user_message="big",
                )
            ]
            # 工具结果事件依然 ok=True（截断不是失败）
            tr = next(e for e in events if e.get("type") == "tool_result")
            assert tr["ok"] is True
        finally:
            toolbase.REGISTRY.pop("big_tool", None)


class TestIntermediateTextStreamedOnce:
    """工具轮中模型同时发了文本 + tool_use：文本只发一次（不在 _agent_loop + _emit_tool_round 两边重复）。"""

    async def test_text_in_tool_round_not_duplicated(
        self, monkeypatch, seeded_db, fake_stream, make_resp, _register_echo
    ) -> None:
        # 第一轮：text=正在查询 + tool_use；live=False（首轮）故不实时流
        responses = [
            make_resp(
                text="正在查询",
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "echo_tool", "input": {"x": "1"}}],
            ),
            make_resp(text="draft"),
            make_resp(text="done"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))
        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="hi",
            )
        ]
        text_events = [e for e in events if e.get("type") == "text"]
        joined = "".join(e["text"] for e in text_events)
        assert joined.count("正在查询") == 1


class TestAssistantPersistencePerRound:
    """工具轮 assistant block 当轮入库；draft 轮（self-check 前 end_turn）不入库；
    final 轮（self-check 后）入库。最终 messages 应有 2 条 assistant（工具轮 + final）。"""

    async def test_assistant_persisted_for_tool_round_and_final_only(
        self, monkeypatch, seeded_db, fake_stream, make_resp, _register_echo
    ) -> None:
        responses = [
            make_resp(
                text="查询中",
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "echo_tool", "input": {"x": "a"}}],
            ),
            make_resp(text="draft text"),  # 不入库
            make_resp(text="final text"),  # 入库
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))
        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="go",
        ):
            pass
        msgs = await list_messages(conv)
        assistant_rows = [m for m in msgs if m["role"] == "assistant"]
        assert len(assistant_rows) == 2
        # 内容里能找到 "final text" 与 "查询中"，不应找到 "draft text"
        all_text = " ".join(str(m["content"]) for m in assistant_rows)
        assert "final text" in all_text
        assert "查询中" in all_text
        assert "draft text" not in all_text
