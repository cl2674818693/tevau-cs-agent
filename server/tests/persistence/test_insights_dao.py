"""Persistence: insights.py — 知识缺口 / 工具健康度 / 下钻。

覆盖：knowledge_gaps（4 项信号计数 + 时间窗）, tool_health（按工具聚合 / 防除零）,
gap_conversations（kind 白名单 / 非法 raise）。
"""

import pytest

from ai_engine.persistence import (
    audit,
    conversations as conv,
    feedback,
    insights,
)
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestKnowledgeGaps:
    async def test_zero_state(self, db_ready) -> None:
        gaps = await insights.knowledge_gaps(None, None)
        assert gaps == {
            "out_of_scope": 0,
            "failed_turns": 0,
            "thumbs_down": 0,
            "human_handoff": 0,
        }

    async def test_counts_each_signal(self, db_ready) -> None:
        # out_of_scope: 1 user msg with topic_verdict='no'
        c1 = await conv.create_conversation("c", "U1")
        t1 = await conv.append_user_turn(c1, "x", client_message_id=None)
        await conv.finalize_turn(t1, "done")
        await conv.set_turn_verdict(t1, "no")
        # failed_turns: 1
        t2 = await conv.append_user_turn(c1, "y", client_message_id=None)
        await conv.finalize_turn(t2, "failed", error_code="X")
        # thumbs_down
        m = await conv.append_message(c1, "assistant", "a")
        await feedback.add_feedback(c1, m, "down", None, "U1", "c")
        # human_handoff
        c2 = await conv.create_conversation("c", "U2")
        await conv.set_mode(c2, "human_pending")

        gaps = await insights.knowledge_gaps(None, None)
        assert gaps["out_of_scope"] == 1
        assert gaps["failed_turns"] == 1
        assert gaps["thumbs_down"] == 1
        assert gaps["human_handoff"] == 1

    async def test_date_window_isolates(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        t = await conv.append_user_turn(c, "x", client_message_id=None)
        await conv.finalize_turn(t, "failed", error_code="X")
        gaps = await insights.knowledge_gaps("1900-01-01 00:00:00", "1900-01-02 00:00:00")
        assert gaps["failed_turns"] == 0


class TestToolHealth:
    async def test_groups_by_tool(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        await audit.log_tool_call(c, "lookup_user", {}, 0, 0, False, None, is_empty=False)
        await audit.log_tool_call(c, "lookup_user", {}, 0, 0, False, None, is_empty=True)
        await audit.log_tool_call(c, "lookup_card", {}, 0, 0, True, "x", is_empty=False)
        rows = await insights.tool_health(None, None)
        by = {r["tool_name"]: r for r in rows}
        assert by["lookup_user"]["calls"] == 2
        assert by["lookup_user"]["empty"] == 1
        assert by["lookup_user"]["empty_rate"] == 0.5
        assert by["lookup_card"]["rejected"] == 1
        # 排序：按 calls DESC
        assert rows[0]["tool_name"] == "lookup_user"

    async def test_zero_calls_returns_empty(self, db_ready) -> None:
        assert await insights.tool_health(None, None) == []

    async def test_empty_rate_defends_div_zero(self, db_ready) -> None:
        """虽然 calls=0 不会进 SELECT 输出，但 Python 防御已写在 source。
        这里只验证 calls=N 时正常算。"""
        c = await conv.create_conversation("c", "U1")
        await audit.log_tool_call(c, "t", {}, 0, 0, False, None, is_empty=False)
        rows = await insights.tool_health(None, None)
        assert rows[0]["empty_rate"] == 0.0


class TestGapConversations:
    async def test_invalid_kind_raises(self, db_ready) -> None:
        with pytest.raises(ValueError):
            await insights.gap_conversations("bogus", None, None)

    async def test_out_of_scope_drill_down(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        t = await conv.append_user_turn(c, "x", client_message_id=None)
        await conv.finalize_turn(t, "done")
        await conv.set_turn_verdict(t, "no")
        rows = await insights.gap_conversations("out_of_scope", None, None)
        assert rows[0]["conversation_id"] == c

    async def test_failed_drill_down(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        t = await conv.append_user_turn(c, "x", client_message_id=None)
        await conv.finalize_turn(t, "failed", error_code="X")
        rows = await insights.gap_conversations("failed", None, None)
        assert rows[0]["conversation_id"] == c

    async def test_thumbs_down_drill_down(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        m = await conv.append_message(c, "assistant", "a")
        await feedback.add_feedback(c, m, "down", None, "U1", "c")
        rows = await insights.gap_conversations("thumbs_down", None, None)
        assert rows[0]["conversation_id"] == c

    async def test_human_handoff_drill_down(self, db_ready) -> None:
        c = await conv.create_conversation("c", "U1")
        await conv.set_mode(c, "human_pending")
        rows = await insights.gap_conversations("human_handoff", None, None)
        assert rows[0]["conversation_id"] == c

    async def test_limit(self, db_ready) -> None:
        for _ in range(5):
            c = await conv.create_conversation("c", "U")
            await conv.set_mode(c, "human_pending")
        rows = await insights.gap_conversations("human_handoff", None, None, limit=2)
        assert len(rows) == 2
