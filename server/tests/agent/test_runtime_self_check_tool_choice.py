"""验证：self-check 修订轮硬禁工具（tool_choice={"type":"none"}）

针对 runtime.py:452 + anthropic_client.py:54 这次 diff 的覆盖。

被测对象：
- build_messages_request(tool_choice=...) 透传
- _agent_loop 在 self_check_done=True 那一轮请求体中 tool_choice="none"
"""
from types import SimpleNamespace

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.integrations.anthropic_client import build_messages_request
from ai_engine.persistence.conversations import create_conversation


async def _new_conv() -> int:
    return await create_conversation("c", "U001")


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}
    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


# ============ 1. build_messages_request 单元 ============


class TestBuildMessagesRequestToolChoice:
    def test_tool_choice_none_param_omits_field(self) -> None:
        """tool_choice 参数不传 → 请求体里就没有 tool_choice 字段（Anthropic 默认 auto）。"""
        req = build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m"
        )
        assert "tool_choice" not in req

    def test_tool_choice_none_type_set_explicitly(self) -> None:
        """tool_choice={"type":"none"} → 请求体里 tool_choice 字段透传。"""
        req = build_messages_request(
            system_blocks=[], messages=[], tools=None, model="m",
            tool_choice={"type": "none"},
        )
        assert req["tool_choice"] == {"type": "none"}

    def test_tool_choice_any_type_passthrough(self) -> None:
        """其他 tool_choice 形态也能透传（auto / tool 名等）。"""
        req = build_messages_request(
            system_blocks=[], messages=[], tools=[], model="m",
            tool_choice={"type": "tool", "name": "query_user"},
        )
        assert req["tool_choice"] == {"type": "tool", "name": "query_user"}


# ============ 2. _agent_loop self-check 轮 tool_choice ============

class TestAgentLoopSelfCheckToolChoice:
    """关键断言：第 1 轮请求 tool_choice 缺失，第 2 轮（self-check 后）tool_choice={"type":"none"}。"""

    async def test_self_check_round_forbids_tools(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        # 两轮都返回 end_turn 文本：第 1 轮触发 self-check，第 2 轮是修订后输出
        responses = [make_resp(text="draft"), make_resp(text="final")]
        stream_mock = fake_stream(responses)
        monkeypatch.setattr(_ac._client.messages, "stream", stream_mock)

        conv = await _new_conv()
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="hello",
        ):
            pass

        # stream_mock 应该被调了至少 2 次（首轮 + self-check 修订轮）
        calls = stream_mock.call_args_list
        assert len(calls) >= 2, f"expected ≥2 LLM calls, got {len(calls)}"

        first_req = calls[0].kwargs
        last_req = calls[-1].kwargs

        # 关键断言 1：首轮（草稿轮）没有 tool_choice → 允许 LLM 自由调工具
        assert "tool_choice" not in first_req, (
            f"首轮请求不应有 tool_choice（应让 LLM 自由判断是否调工具）; got {first_req.get('tool_choice')}"
        )

        # 关键断言 2：self-check 修订轮 tool_choice 必须为 {"type":"none"}
        assert last_req.get("tool_choice") == {"type": "none"}, (
            f"self-check 修订轮必须硬禁工具; got tool_choice={last_req.get('tool_choice')}"
        )

    async def test_self_check_round_request_includes_self_check_block(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        """除了 tool_choice，self-check 修订轮的 messages 必须包含 self-check 注入块。"""
        responses = [make_resp(text="draft"), make_resp(text="final")]
        stream_mock = fake_stream(responses)
        monkeypatch.setattr(_ac._client.messages, "stream", stream_mock)

        conv = await _new_conv()
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="hello",
        ):
            pass

        last_req = stream_mock.call_args_list[-1].kwargs
        last_user_msgs = [
            m for m in last_req["messages"]
            if m["role"] == "user"
        ]
        # 最后一条 user 消息是 self-check 注入（"在你给出上面这段最终回复之前..."）
        assert any(
            "请按以下规则做一次审视" in m["content"]
            for m in last_user_msgs
        ), "self-check 修订轮必须把 self_check.md 作为新 user message 注入到 messages"
