"""Agent runtime: 回合状态机（messages.status / error_code / topic_verdict / client_message_id）

被测对象：persistence.conversations.append_user_turn / finalize_turn / set_turn_verdict /
find_completed_turn / get_turn_assistant_texts。
runtime 端：run_turn 成功路径下 status=done；fail-soft 路径下 status=failed + error_code。

mock 策略：直接打 persistence + 走 fake_stream 跑一遍 run_turn。
"""

import pytest

from ai_engine.agent import runtime as rt
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence import db
from ai_engine.persistence.conversations import (
    append_message,
    append_user_turn,
    create_conversation,
    finalize_turn,
    find_completed_turn,
    get_turn_assistant_texts,
    list_messages,
    set_turn_verdict,
)


@pytest.fixture(autouse=True)
def _silence_budget(monkeypatch):
    async def _ok(_ut, _sid, _it, _ot, model=None):  # noqa: ARG001
        return True, {"used": 1, "limit": 1000, "warn": False}

    monkeypatch.setattr(rt, "check_and_record", _ok)
    yield


class TestAppendUserTurn:
    """user 行入库时 status=processing；其它列默认值正确。"""

    async def test_user_turn_initial_status_processing(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "hello", client_message_id="cm-1")
        row = await db.fetch_one(
            "SELECT role, status, client_message_id, error_code FROM messages WHERE id=:id",
            {"id": tid},
        )
        assert row["role"] == "user"
        assert row["status"] == "processing"
        assert row["client_message_id"] == "cm-1"
        assert row["error_code"] is None

    async def test_user_turn_without_cmid(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "hi", client_message_id=None)
        row = await db.fetch_one(
            "SELECT client_message_id FROM messages WHERE id=:id", {"id": tid}
        )
        assert row["client_message_id"] is None


class TestFinalizeTurn:
    """finalize_turn: done 清空 error_code；failed 写入 error_code。"""

    async def test_finalize_done(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "x", None)
        await finalize_turn(tid, "done")
        row = await db.fetch_one(
            "SELECT status, error_code FROM messages WHERE id=:id", {"id": tid}
        )
        assert row["status"] == "done"
        assert row["error_code"] is None

    async def test_finalize_failed_with_code(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "x", None)
        await finalize_turn(tid, "failed", "INTERNAL_ERROR")
        row = await db.fetch_one(
            "SELECT status, error_code FROM messages WHERE id=:id", {"id": tid}
        )
        assert row["status"] == "failed"
        assert row["error_code"] == "INTERNAL_ERROR"

    async def test_finalize_can_overwrite_status(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "x", None)
        await finalize_turn(tid, "done")
        await finalize_turn(tid, "failed", "STALE_RECLAIMED")
        row = await db.fetch_one(
            "SELECT status, error_code FROM messages WHERE id=:id", {"id": tid}
        )
        assert row["status"] == "failed"
        assert row["error_code"] == "STALE_RECLAIMED"


class TestSetTurnVerdict:
    async def test_verdict_persisted(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "x", None)
        await set_turn_verdict(tid, "no")
        row = await db.fetch_one(
            "SELECT topic_verdict FROM messages WHERE id=:id", {"id": tid}
        )
        assert row["topic_verdict"] == "no"


class TestFindCompletedTurn:
    """幂等：同一 client_message_id 已完成（status=done）的 user 行可被检索到。"""

    async def test_returns_completed_user_row(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "hi", "cm-1")
        await finalize_turn(tid, "done")
        row = await find_completed_turn(conv, "cm-1")
        assert row is not None
        assert row["id"] == tid

    async def test_returns_none_for_processing(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        await append_user_turn(conv, "hi", "cm-1")
        # 未 finalize → status=processing → 不返回
        assert await find_completed_turn(conv, "cm-1") is None

    async def test_returns_none_for_failed(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid = await append_user_turn(conv, "hi", "cm-1")
        await finalize_turn(tid, "failed", "INTERNAL_ERROR")
        assert await find_completed_turn(conv, "cm-1") is None

    async def test_returns_latest_when_multiple(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        tid1 = await append_user_turn(conv, "a", "cm-1")
        await finalize_turn(tid1, "done")
        tid2 = await append_user_turn(conv, "b", "cm-1")
        await finalize_turn(tid2, "done")
        row = await find_completed_turn(conv, "cm-1")
        assert row["id"] == tid2  # 取最大 id


class TestGetTurnAssistantTexts:
    """取某个 turn(user 行)之后到下一条 user 行之前的所有 assistant content。"""

    async def test_collects_until_next_user(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        u1 = await append_user_turn(conv, "ask", None)
        await append_message(conv, role="assistant", content="reply1")
        await append_message(conv, role="assistant", content="reply2")
        await append_user_turn(conv, "next", None)  # 边界
        await append_message(conv, role="assistant", content="afterwards")

        out = await get_turn_assistant_texts(conv, u1)
        assert out == ["reply1", "reply2"]

    async def test_empty_when_no_assistant(self, seeded_db) -> None:
        conv = await create_conversation("c", "U001")
        u1 = await append_user_turn(conv, "ask", None)
        assert await get_turn_assistant_texts(conv, u1) == []


class TestRuntimeFullCycleStatus:
    """run_turn 走完后 status=done；fail-soft 路径下 status=failed。"""

    async def test_run_turn_marks_done(
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
            user_message="hi",
        ):
            pass
        msgs = await list_messages(conv)
        user_row = next(m for m in msgs if m["role"] == "user")
        assert user_row["status"] == "done"
        assert user_row["error_code"] is None

    async def test_run_turn_marks_failed_on_llm_exception(
        self, monkeypatch, seeded_db
    ) -> None:
        def _bad(**_k):
            raise TimeoutError("x")

        monkeypatch.setattr(_ac._client.messages, "stream", _bad)
        conv = await create_conversation("c", "U001")
        async for _ in rt.run_turn(
            conversation_id=conv,
            user_type="c",
            subject_id="U001",
            user_message="hi",
        ):
            pass
        msgs = await list_messages(conv)
        user_row = next(m for m in msgs if m["role"] == "user")
        assert user_row["status"] == "failed"
        assert user_row["error_code"] == "INTERNAL_ERROR"
