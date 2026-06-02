"""Persistence: agent_ratings.py — 用户对人工客服的 1-5 星评分。

覆盖：record（rating 范围校验 / 入库）, get_for_conversation（subject 隔离 / 取最新）,
aggregate_by_staff（count/avg 防除零）, list_for_admin（多过滤 / 分页）。
"""

import pytest

from ai_engine.persistence import agent_ratings, conversations as conv
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestRecord:
    @pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
    async def test_valid_rating(self, db_ready, conv_id, rating: int) -> None:
        rid = await agent_ratings.record(conv_id, "s1", "U1", "c", rating, "ok")
        assert rid > 0

    @pytest.mark.parametrize("rating", [0, 6, -1, 10])
    async def test_invalid_rating_raises(self, db_ready, conv_id, rating: int) -> None:
        with pytest.raises(ValueError):
            await agent_ratings.record(conv_id, "s1", "U1", "c", rating, None)

    async def test_null_comment_ok(self, db_ready, conv_id) -> None:
        rid = await agent_ratings.record(conv_id, "s1", "U1", "c", 5, None)
        assert rid > 0


class TestGetForConversation:
    async def test_returns_latest(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 3, "ok")
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, "good")
        row = await agent_ratings.get_for_conversation(conv_id, "U1")
        assert row is not None and row["rating"] == 5

    async def test_subject_isolation(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, None)
        # 不同 subject 不应看见 U1 的评分
        assert await agent_ratings.get_for_conversation(conv_id, "U2") is None

    async def test_no_rating_returns_none(self, db_ready, conv_id) -> None:
        assert await agent_ratings.get_for_conversation(conv_id, "U1") is None


class TestAggregateByStaff:
    async def test_avg_and_count(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, None)
        await agent_ratings.record(conv_id, "s1", "U2", "c", 3, None)
        agg = await agent_ratings.aggregate_by_staff("s1")
        assert agg["count"] == 2
        assert agg["avg_rating"] == 4.0

    async def test_no_data_zero(self, db_ready) -> None:
        agg = await agent_ratings.aggregate_by_staff("ghost")
        assert agg == {"count": 0, "avg_rating": 0.0}

    async def test_date_window(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, None)
        # 过去窗口拿不到
        agg = await agent_ratings.aggregate_by_staff(
            "s1", date_from="1900-01-01 00:00:00", date_to="1900-01-02 00:00:00"
        )
        assert agg["count"] == 0


class TestListForAdmin:
    async def test_all_filters_none(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, "ok")
        await agent_ratings.record(conv_id, "s2", "U2", "c", 3, "meh")
        rows = await agent_ratings.list_for_admin()
        assert len(rows) == 2

    async def test_filter_by_staff(self, db_ready, conv_id) -> None:
        await agent_ratings.record(conv_id, "s1", "U1", "c", 5, None)
        await agent_ratings.record(conv_id, "s2", "U2", "c", 5, None)
        rows = await agent_ratings.list_for_admin(staff_id="s2")
        assert [r["staff_id"] for r in rows] == ["s2"]

    async def test_limit_offset(self, db_ready, conv_id) -> None:
        for i in range(5):
            await agent_ratings.record(conv_id, "s1", f"U{i}", "c", 5, None)
        rows = await agent_ratings.list_for_admin(limit=2, offset=2)
        assert len(rows) == 2

    async def test_ordered_desc(self, db_ready, conv_id) -> None:
        ids = []
        for i in range(3):
            ids.append(await agent_ratings.record(conv_id, "s1", f"U{i}", "c", 5, None))
        rows = await agent_ratings.list_for_admin()
        assert [r["id"] for r in rows] == list(reversed(ids))
