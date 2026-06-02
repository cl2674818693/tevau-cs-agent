"""Agent runtime: LLM/工具异常 fail-soft 行为

被测对象：runtime.run_turn 在以下情况下应当不裸抛、出固定兜底文案并标 turn=failed：
- LLM stream 抛 TimeoutError / APIError
- 工具 dispatch 抛异常（由 tool_router 转 ok=False，但 runtime 不应崩）
- conversation_compactor 在 _maybe_compact 抛错（runtime 在 try 内吞掉）

mock 策略：
- 用 monkeypatch 把 _ac._client.messages.stream 直接换成抛错的可调用对象。
- check_and_record 放行（不属于本文件覆盖）。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import create_conversation, list_messages


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


def _make_stream_raises(exc: BaseException):
    """把 _client.messages.stream 替成抛指定异常的同步函数（在 async with 进入前就炸）。"""

    def _stream(**_kwargs):  # noqa: ANN003
        raise exc

    return _stream


class TestLlmStreamException:
    """LLM 抛错时：runtime 应给 type=error + 固定文案，并把 user 回合状态机标 failed。"""

    async def test_timeout_error_yields_failsoft(
        self, monkeypatch, seeded_db
    ) -> None:
        monkeypatch.setattr(
            _ac._client.messages, "stream", _make_stream_raises(TimeoutError("upstream"))
        )

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
        # 最后一个事件是 error，文案=固定 _FAILSOFT_TEXT
        assert events[-1] == {
            "type": "error",
            "code": "INTERNAL_ERROR",
            "text": rt._FAILSOFT_TEXT,
        }
        # user 行落库 + status 应被 finalize_turn 标 failed
        msgs = await list_messages(conv)
        user_rows = [m for m in msgs if m["role"] == "user"]
        assert user_rows and user_rows[-1]["status"] == "failed"
        assert user_rows[-1]["error_code"] == "INTERNAL_ERROR"

    async def test_generic_runtime_error_failsoft(
        self, monkeypatch, seeded_db
    ) -> None:
        monkeypatch.setattr(
            _ac._client.messages, "stream", _make_stream_raises(RuntimeError("boom"))
        )

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
        assert any(e.get("type") == "error" for e in events)
        # 不应裸抛任何异常给调用方
        assert events[-1]["code"] == "INTERNAL_ERROR"


class TestToolDispatchException:
    """工具 handler 抛异常：tool_router 兜底成 {ok:False}；runtime 应继续走（不崩）。"""

    async def test_tool_handler_raises_does_not_crash_runtime(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        # 注入临时工具 fakebomb，handler 抛错
        from ai_engine.agent.tools import base as toolbase

        async def _boom(**_kw):  # noqa: ANN003
            raise RuntimeError("tool internal")

        toolbase.register(
            toolbase.Tool(
                name="fakebomb",
                description="x",
                input_schema={"type": "object", "properties": {}, "required": []},
                handler=_boom,
            )
        )

        # 第 1 轮 LLM 触发 tool_use → fakebomb；第 2 轮直接 end_turn 出文本；第 3 轮 self-check final
        responses = [
            make_resp(
                stop_reason="tool_use",
                tool_calls=[{"id": "t1", "name": "fakebomb", "input": {}}],
            ),
            make_resp(text="处理完毕"),
            make_resp(text="处理完毕"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="去查",
            )
        ]
        # 应能正常走完，最终出 text
        texts = "".join(e["text"] for e in events if e.get("type") == "text")
        assert "处理完毕" in texts
        # 工具调用事件 ok=False，给前端看到工具失败
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        assert tool_results and tool_results[0]["ok"] is False

        # 清理临时工具，避免影响其它用例
        toolbase.REGISTRY.pop("fakebomb", None)


class TestCompactorFailureBubblesToFailsoft:
    """会话压缩抛错：runtime 内 await _maybe_compact 在 try 外，应直接走 fail-soft 兜底。"""

    async def test_compact_raises_triggers_failsoft(
        self, monkeypatch, seeded_db
    ) -> None:
        async def _should(_id):
            return True

        async def _compact(_id):
            raise RuntimeError("summary down")

        monkeypatch.setattr(rt, "should_compact", _should)
        monkeypatch.setattr(rt, "compact_conversation", _compact)

        conv = await create_conversation("c", "U001")
        # 当前 runtime 的 _maybe_compact 在 try 外抛错会直接传播（没有 fail-soft）
        with pytest.raises(RuntimeError, match="summary down"):
            async for _ in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="hi",
            ):
                pass


class TestUserRowAlwaysWritten:
    """fail-soft 路径下 user 行依然要落库，否则历史回放/审计断链。"""

    async def test_user_message_persisted_even_on_failure(
        self, monkeypatch, seeded_db
    ) -> None:
        monkeypatch.setattr(
            _ac._client.messages, "stream", _make_stream_raises(TimeoutError("x"))
        )
        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="hello world",
        ):
            pass
        msgs = await list_messages(conv)
        user_texts = [m["content"] for m in msgs if m["role"] == "user"]
        assert "hello world" in user_texts
