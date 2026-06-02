"""Persistence: audit.py — 工具调用审计写入 + 跨会话最近列表 + 计数。

覆盖：log_tool_call（is_empty 三态：True/False/None）, list_audits,
count_recent_audits, recent_audits（rejected_only / empty_only / tool_name /
conversation_id / before_id / offset 多组合）。
"""

import asyncio
import json

import pytest

from ai_engine.persistence import audit, conversations as conv
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestLogToolCall:
    async def test_basic_insert_returns_id(self, db_ready, conv_id) -> None:
        aid = await audit.log_tool_call(
            conv_id, "tool_a", {"k": 1}, 100, 5, False, None,
            result_count=3, is_empty=False, subject_id="U1", user_type="c",
        )
        assert aid > 0

    async def test_params_serialized_as_json(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(
            conv_id, "t", {"q": "你好"}, 0, 0, False, None
        )
        rows = await audit.list_audits(conv_id)
        assert json.loads(rows[0]["params_json"]) == {"q": "你好"}

    async def test_is_empty_true_writes_one(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None, is_empty=True)
        rows = await audit.list_audits(conv_id)
        assert rows[0]["is_empty"] == 1

    async def test_is_empty_false_writes_zero(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None, is_empty=False)
        rows = await audit.list_audits(conv_id)
        assert rows[0]["is_empty"] == 0

    async def test_is_empty_none_writes_null(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None)  # is_empty 默认 None
        rows = await audit.list_audits(conv_id)
        assert rows[0]["is_empty"] is None

    async def test_rejected_flag_and_reason(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 1, True, "bu_id mismatch")
        rows = await audit.list_audits(conv_id)
        assert rows[0]["rejected"] == 1
        assert rows[0]["reject_reason"] == "bu_id mismatch"


class TestListAuditsByConversation:
    async def test_ordered_by_id(self, db_ready, conv_id) -> None:
        for i in range(3):
            await audit.log_tool_call(conv_id, f"t{i}", {}, 0, 0, False, None)
        rows = await audit.list_audits(conv_id)
        assert [r["tool_name"] for r in rows] == ["t0", "t1", "t2"]

    async def test_empty_returns_empty(self, db_ready, conv_id) -> None:
        assert await audit.list_audits(conv_id) == []


class TestRecentAudits:
    async def test_default_newest_first(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await audit.log_tool_call(c1, "a", {}, 0, 0, False, None)
        await audit.log_tool_call(c2, "b", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=10)
        assert [r["tool_name"] for r in rows] == ["b", "a"]

    async def test_limit_respected(self, db_ready, conv_id) -> None:
        for i in range(5):
            await audit.log_tool_call(conv_id, f"t{i}", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=2)
        assert len(rows) == 2

    async def test_offset(self, db_ready, conv_id) -> None:
        for i in range(5):
            await audit.log_tool_call(conv_id, f"t{i}", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=2, offset=2)
        assert [r["tool_name"] for r in rows] == ["t2", "t1"]

    async def test_rejected_only(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "ok", {}, 0, 0, False, None)
        await audit.log_tool_call(conv_id, "rej", {}, 0, 0, True, "no perm")
        rows = await audit.recent_audits(limit=10, rejected_only=True)
        assert [r["tool_name"] for r in rows] == ["rej"]

    async def test_empty_only(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "e", {}, 0, 0, False, None, is_empty=True)
        await audit.log_tool_call(conv_id, "ne", {}, 0, 0, False, None, is_empty=False)
        rows = await audit.recent_audits(limit=10, empty_only=True)
        assert [r["tool_name"] for r in rows] == ["e"]

    async def test_filter_by_tool_name(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "lookup_user", {}, 0, 0, False, None)
        await audit.log_tool_call(conv_id, "lookup_card", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=10, tool_name="lookup_card")
        assert [r["tool_name"] for r in rows] == ["lookup_card"]

    async def test_filter_by_conversation(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await audit.log_tool_call(c1, "a", {}, 0, 0, False, None)
        await audit.log_tool_call(c2, "b", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=10, conversation_id=c1)
        assert [r["tool_name"] for r in rows] == ["a"]

    async def test_before_id_cursor(self, db_ready, conv_id) -> None:
        ids = []
        for i in range(4):
            ids.append(
                await audit.log_tool_call(conv_id, f"t{i}", {}, 0, 0, False, None)
            )
        rows = await audit.recent_audits(limit=10, before_id=ids[2])
        # 严格 id < ids[2]：返回 t1, t0
        assert [r["tool_name"] for r in rows] == ["t1", "t0"]

    async def test_combined_filters(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None, is_empty=True)
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, True, "x")
        await audit.log_tool_call(conv_id, "other", {}, 0, 0, True, "x")
        rows = await audit.recent_audits(
            limit=10, rejected_only=True, tool_name="t"
        )
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "t" and rows[0]["rejected"] == 1


class TestCountRecentAudits:
    async def test_total_no_filters(self, db_ready, conv_id) -> None:
        for _ in range(3):
            await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None)
        assert await audit.count_recent_audits() == 3

    async def test_count_with_filters_matches_list(self, db_ready, conv_id) -> None:
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, True, "x")
        await audit.log_tool_call(conv_id, "t", {}, 0, 0, False, None)
        rows = await audit.recent_audits(limit=10, rejected_only=True)
        cnt = await audit.count_recent_audits(rejected_only=True)
        assert cnt == len(rows) == 1

    async def test_empty(self, db_ready) -> None:
        assert await audit.count_recent_audits() == 0
