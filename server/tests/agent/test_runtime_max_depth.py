"""Agent runtime: max_tool_depth 上限

被测对象：CostGuard.can_call_again / runtime._run_tools 达到深度上限后回写 is_error=True
的 tool_result（content="ERROR: 达到工具调用深度上限..."）。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.agent.cost_guard import CostGuard
from ai_engine.agent.tools import base as toolbase
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestCostGuardBasics:
    """CostGuard 行为矩阵：达到 max_depth 后 can_call_again=False。"""

    def test_initial_can_call(self) -> None:
        g = CostGuard(max_depth=3, max_result_bytes=1024)
        assert g.can_call_again() is True

    def test_after_max_calls_cannot_call(self) -> None:
        g = CostGuard(max_depth=2, max_result_bytes=1024)
        g.note_call()
        g.note_call()
        assert g.can_call_again() is False

    def test_zero_depth_immediately_blocks(self) -> None:
        g = CostGuard(max_depth=0, max_result_bytes=1024)
        assert g.can_call_again() is False

    def test_maybe_truncate_under_limit_passthrough(self) -> None:
        g = CostGuard(max_depth=1, max_result_bytes=1024)
        payload = "abc"
        out, truncated = g.maybe_truncate(payload)
        assert out == "abc"
        assert truncated is False

    def test_maybe_truncate_over_limit_cuts(self) -> None:
        g = CostGuard(max_depth=1, max_result_bytes=4)
        payload = "1234567890"
        out, truncated = g.maybe_truncate(payload)
        assert truncated is True
        assert len(out.encode("utf-8")) <= 4

    def test_truncate_does_not_break_utf8(self) -> None:
        g = CostGuard(max_depth=1, max_result_bytes=2)
        # 中文每字 3 字节，截断点 errors=ignore 防止半字符
        out, _ = g.maybe_truncate("一二三")
        # 不会 raise UnicodeDecodeError
        assert isinstance(out, str)


class TestRuntimeRespectsMaxDepth:
    """run_turn 在工具循环里达 max_depth 后，超出部分 tool_result 应为 is_error=True 的回执。"""

    async def test_depth_exceeded_returns_error_tool_result(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        from ai_engine.config import settings as _settings

        # 把全局 max_tool_depth 设为 1：第 1 次工具放行；第 2 次 LLM 又请求工具 → 应被拒
        monkeypatch.setattr(_settings, "max_tool_depth", 1)

        calls = []

        async def _h(**kw):  # noqa: ANN003
            calls.append(kw)
            return {"ok": True}

        toolbase.register(
            toolbase.Tool(
                name="ping_tool",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_h,
            )
        )
        try:
            responses = [
                make_resp(
                    stop_reason="tool_use",
                    tool_calls=[{"id": "t1", "name": "ping_tool", "input": {}}],
                ),
                make_resp(
                    stop_reason="tool_use",
                    tool_calls=[{"id": "t2", "name": "ping_tool", "input": {}}],
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
            # ping_tool 仅被调一次（第 2 次因 max_depth 不再执行）
            assert len(calls) == 1
            # 但流出的事件中仍有 2 个 tool_call（这是模型决定的）；
            # 真正的"达上限"反映在 messages 历史里的 tool_result block，事件流没显式标记
            tool_calls_events = [e for e in events if e.get("type") == "tool_call"]
            assert len(tool_calls_events) == 2
        finally:
            toolbase.REGISTRY.pop("ping_tool", None)

    async def test_run_tools_helper_blocks_beyond_depth(self) -> None:
        """直接打 _run_tools：guard 不允许新调用时返回 ERROR 文案的 tool_result block。"""
        guard = CostGuard(max_depth=0, max_result_bytes=1024)
        tool_calls = [{"id": "t1", "name": "anything", "input": {}}]
        blocks, events = await rt._run_tools(
            tool_calls,
            guard,
            user_type="c",
            subject_id="U001",
            conversation_id=1,
        )
        assert blocks and blocks[0]["is_error"] is True
        assert "深度上限" in blocks[0]["content"]
        # events 不会被推（因 continue 跳过）
        assert events == []
