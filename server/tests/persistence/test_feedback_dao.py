"""Persistence: feedback.py — 消息级 👍/👎 反馈。

覆盖：add_feedback（rating 约束 up/down）, list_feedback（按时间序）。
"""

import pytest

from ai_engine.persistence import conversations as conv, feedback
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestAddFeedback:
    @pytest.mark.parametrize("rating", ["up", "down"])
    async def test_valid_rating(self, db_ready, conv_id, rating: str) -> None:
        mid = await conv.append_message(conv_id, "assistant", "a")
        fid = await feedback.add_feedback(conv_id, mid, rating, None, "U1", "c")
        assert fid > 0

    async def test_invalid_rating_raises(self, db_ready, conv_id) -> None:
        """ck_feedback_rating: rating IN ('up','down')。"""
        mid = await conv.append_message(conv_id, "assistant", "a")
        with pytest.raises(Exception):  # noqa: B017 check constraint
            await feedback.add_feedback(conv_id, mid, "meh", None, "U1", "c")

    async def test_reason_optional(self, db_ready, conv_id) -> None:
        mid = await conv.append_message(conv_id, "assistant", "a")
        fid = await feedback.add_feedback(conv_id, mid, "down", "解决不了", "U1", "c")
        rows = await feedback.list_feedback(conv_id)
        assert rows[0]["id"] == fid
        assert rows[0]["reason"] == "解决不了"


class TestListFeedback:
    async def test_ordered_by_id(self, db_ready, conv_id) -> None:
        mid = await conv.append_message(conv_id, "assistant", "a")
        f1 = await feedback.add_feedback(conv_id, mid, "up", None, "U1", "c")
        f2 = await feedback.add_feedback(conv_id, mid, "down", "x", "U1", "c")
        rows = await feedback.list_feedback(conv_id)
        assert [r["id"] for r in rows] == [f1, f2]

    async def test_empty_returns_empty(self, db_ready, conv_id) -> None:
        assert await feedback.list_feedback(conv_id) == []

    async def test_isolated_per_conversation(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        m1 = await conv.append_message(c1, "assistant", "a")
        m2 = await conv.append_message(c2, "assistant", "b")
        await feedback.add_feedback(c1, m1, "up", None, "U1", "c")
        await feedback.add_feedback(c2, m2, "down", None, "U2", "c")
        assert len(await feedback.list_feedback(c1)) == 1
        assert len(await feedback.list_feedback(c2)) == 1
