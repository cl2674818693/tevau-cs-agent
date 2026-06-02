"""Agent runtime: 触发 conversation_compactor

被测对象：
- conversation_compactor._render_history / _summarize / compact_conversation
- runtime._maybe_compact 触发压缩并 yield system 事件 + seed messages
"""

import pytest

from ai_engine.agent import conversation_compactor as cc
from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import (
    append_message,
    create_conversation,
    get_conversation,
    list_messages,
)


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestRenderHistory:
    def test_render_basic(self) -> None:
        out = cc._render_history(
            [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        )
        assert out == "[user] hi\n[assistant] hello"

    def test_render_missing_fields(self) -> None:
        out = cc._render_history([{"role": "system"}, {"content": "x"}])
        assert "[system]" in out
        assert "[] x" in out


class TestSummarizeCalls:
    """_summarize 用 messages.create 而非 stream；返回所有 text block 拼接 strip。"""

    async def test_summarize_concat_strip(self, monkeypatch) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        resp = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="A "),
                SimpleNamespace(type="text", text="B\n"),
            ]
        )
        monkeypatch.setattr(_ac._client.messages, "create", AsyncMock(return_value=resp))
        assert await cc._summarize("hist") == "A B"

    async def test_summarize_empty_falls_back(self, monkeypatch) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        resp = SimpleNamespace(content=[])
        monkeypatch.setattr(_ac._client.messages, "create", AsyncMock(return_value=resp))
        assert await cc._summarize("hist") == "（无可总结内容）"

    async def test_summarize_propagates_upstream_error(self, monkeypatch) -> None:
        async def _boom(**_kw):  # noqa: ANN003
            raise RuntimeError("api down")

        monkeypatch.setattr(_ac._client.messages, "create", _boom)
        with pytest.raises(RuntimeError, match="api down"):
            await cc._summarize("x")


class TestCompactConversation:
    """compact_conversation: 总结老会话、开新会话、归档老会话。"""

    async def test_compact_creates_new_and_archives_old(
        self, monkeypatch, seeded_db
    ) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        old = await create_conversation("c", "U001")
        await append_message(old, role="user", content="hi")
        await append_message(old, role="assistant", content="hello")

        resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="摘要内容")]
        )
        monkeypatch.setattr(_ac._client.messages, "create", AsyncMock(return_value=resp))

        new_id = await cc.compact_conversation(old)
        assert new_id != old
        # 新会话第一条是 system=摘要
        new_msgs = await list_messages(new_id)
        sys_msg = next(m for m in new_msgs if m["role"] == "system")
        assert sys_msg["content"] == "摘要内容"
        # 老会话被 archived
        from ai_engine.persistence import db

        row = await db.fetch_one(
            "SELECT archived FROM conversations WHERE id=:id", {"id": old}
        )
        assert int(row["archived"]) == 1

    async def test_compact_missing_conv_raises(self, seeded_db) -> None:
        with pytest.raises(ValueError, match="conv not found"):
            await cc.compact_conversation(999_999)


class TestRuntimeMaybeCompactGate:
    """_maybe_compact: should_compact=False 直返 (id, None, [])；True 时新建 + 给 system 事件。"""

    async def test_no_compact_returns_unchanged(self, monkeypatch, seeded_db) -> None:
        async def _no(_id):
            return False

        monkeypatch.setattr(rt, "should_compact", _no)
        conv = await create_conversation("c", "U001")
        new_id, event, msgs = await rt._maybe_compact(conv)
        assert new_id == conv
        assert event is None
        assert msgs == []

    async def test_compact_returns_new_id_and_event(self, monkeypatch, seeded_db) -> None:
        async def _yes(_id):
            return True

        # mock compact_conversation 不打 LLM
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        async def _compact(old_id):
            new = await create_conversation("c", "U001")
            await append_message(new, role="system", content="aaa")
            return new

        monkeypatch.setattr(rt, "should_compact", _yes)
        monkeypatch.setattr(rt, "compact_conversation", _compact)
        _ = SimpleNamespace, AsyncMock  # silence import lint

        conv = await create_conversation("c", "U001")
        new_id, event, seed = await rt._maybe_compact(conv)
        assert new_id != conv
        assert event and event["type"] == "system"
        assert "conversation_id=" in event["text"]
        # seed 含上文摘要
        assert seed and "[上文摘要]" in seed[0]["content"]


class TestRuntimeIntegrationCompactionEmitsEvent:
    """run_turn 入口若 should_compact=True，事件流第一条应是 system 通告。"""

    async def test_run_turn_emits_compact_event_first(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        async def _yes(_id):
            return True

        async def _compact(old_id):
            new = await create_conversation("c", "U001")
            await append_message(new, role="system", content="prev summary")
            return new

        monkeypatch.setattr(rt, "should_compact", _yes)
        monkeypatch.setattr(rt, "compact_conversation", _compact)

        responses = [make_resp(text="hi"), make_resp(text="hi")]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await create_conversation("c", "U001")
        events = [
            e
            async for e in rt.run_turn(
                conversation_id=conv,
                user_type="c",
                subject_id="U001",
                user_message="hello",
            )
        ]
        first = events[0]
        assert first["type"] == "system"
        assert "新对话" in first["text"]

    async def test_inferred_locale_set_after_run(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        monkeypatch.setattr(
            _ac._client.messages,
            "stream",
            fake_stream([make_resp(text="ok"), make_resp(text="ok")]),
        )
        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="你好",  # 中文触发 _detect_locale → zh
        ):
            pass
        row = await get_conversation(conv)
        assert row["inferred_locale"] == "zh"
