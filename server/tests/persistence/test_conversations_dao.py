"""Persistence: conversations.py — 会话与消息 CRUD / 回合管理 / 客服列表筛选。

覆盖所有公开函数：message_content_text(纯), create/get_resumable/get_conversation,
set_inferred_locale, append_message/append_user_turn, finalize_turn,
set_turn_verdict, find_completed_turn, get_turn_assistant_texts,
count_pending/archive/mark_needs_review, count_user_turns, sum_content_chars,
list_messages / list_messages_page / list_recent_messages,
set_mode/get_mode/get_conversation_meta/get_meta_with_risk,
list_for_staff(filter_status/risk_only), save_ai_draft/get_latest_ai_draft/clear_ai_drafts,
append_human_message。

策略：均用 sqlite (temp_db_url + init_db)。仅校验业务可观察行为，不挂 mock。
"""

import asyncio
import json

import pytest

from ai_engine.persistence import conversations as conv
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestMessageContentText:
    """assistant 入库 JSON([{type:text,text:...}]) 还原；其他角色透传。"""

    def test_user_role_returns_as_is(self) -> None:
        assert conv.message_content_text("user", "你好") == "你好"

    def test_human_agent_returns_as_is(self) -> None:
        assert conv.message_content_text("human_agent", "客服回复") == "客服回复"

    def test_assistant_blocks_concat_text(self) -> None:
        c = json.dumps(
            [
                {"type": "text", "text": "hello "},
                {"type": "tool_use", "name": "x"},  # 应忽略
                {"type": "text", "text": "world"},
            ]
        )
        assert conv.message_content_text("assistant", c) == "hello world"

    def test_assistant_invalid_json_fallback(self) -> None:
        """JSON 解析失败：返回原文。"""
        assert conv.message_content_text("assistant", "not-json") == "not-json"

    def test_assistant_non_list_fallback(self) -> None:
        """blocks 非 list：返回原文（防御性）。"""
        c = json.dumps({"type": "text", "text": "x"})  # dict 不是 list
        assert conv.message_content_text("assistant", c) == c

    def test_assistant_empty_list(self) -> None:
        assert conv.message_content_text("assistant", "[]") == ""


class TestCreateAndGetConversation:
    async def test_create_returns_pk(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert isinstance(cid, int) and cid > 0

    async def test_get_conversation_roundtrip(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        row = await conv.get_conversation(cid)
        assert row is not None
        assert row["user_type"] == "c"
        assert row["subject_id"] == "U1"

    async def test_get_conversation_missing(self, db_ready) -> None:
        assert await conv.get_conversation(99999) is None


class TestGetResumable:
    async def test_owner_match_returns_row(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        row = await conv.get_resumable(cid, "c", "U1")
        assert row is not None and row["id"] == cid
        assert row["mode"] == "ai"

    async def test_wrong_user_type_returns_none(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.get_resumable(cid, "b", "U1") is None

    async def test_wrong_subject_returns_none(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.get_resumable(cid, "c", "U2") is None

    async def test_missing_conv_returns_none(self, db_ready) -> None:
        assert await conv.get_resumable(99999, "c", "U1") is None

    async def test_archived_filtered_out(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.archive_conversation(cid)
        assert await conv.get_resumable(cid, "c", "U1") is None


class TestSetInferredLocale:
    async def test_set_and_read(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_inferred_locale(cid, "zh-CN")
        row = await conv.get_conversation(cid)
        assert row is not None and row["inferred_locale"] == "zh-CN"

    async def test_overwrite(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_inferred_locale(cid, "zh")
        await conv.set_inferred_locale(cid, "en-US")
        row = await conv.get_conversation(cid)
        assert row is not None and row["inferred_locale"] == "en-US"


class TestAppendMessage:
    async def test_append_basic(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        mid = await conv.append_message(cid, "assistant", "hi")
        assert mid > 0
        rows = await conv.list_messages(cid)
        assert len(rows) == 1
        assert rows[0]["role"] == "assistant"
        assert rows[0]["content"] == "hi"

    async def test_append_persists_role_and_content(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_message(cid, "assistant", "x")
        rows = await conv.list_messages(cid)
        assert rows[0]["role"] == "assistant"
        assert rows[0]["content"] == "x"
        assert "prompt_version" not in rows[0]


class TestUserTurnLifecycle:
    """append_user_turn → finalize_turn → set_turn_verdict → find_completed_turn 闭环。"""

    async def test_full_turn_done(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "我的卡为啥锁了", client_message_id="cm-1")
        # 起始状态：processing
        rows = await conv.list_messages(cid)
        assert rows[0]["status"] == "processing"
        # done
        await conv.finalize_turn(tid, "done")
        rows = await conv.list_messages(cid)
        assert rows[0]["status"] == "done"
        # verdict
        await conv.set_turn_verdict(tid, "yes")
        rows = await conv.list_messages(cid)
        assert rows[0]["topic_verdict"] == "yes"
        # 幂等查找
        found = await conv.find_completed_turn(cid, "cm-1")
        assert found is not None and found["id"] == tid

    async def test_finalize_failed_writes_error_code(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id="cm-2")
        await conv.finalize_turn(tid, "failed", error_code="INTERNAL_ERROR")
        rows = await conv.list_messages(cid)
        assert rows[0]["status"] == "failed"
        assert rows[0]["error_code"] == "INTERNAL_ERROR"

    async def test_find_completed_turn_processing_excluded(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_user_turn(cid, "x", client_message_id="cm-3")
        # 未 finalize：不返回
        assert await conv.find_completed_turn(cid, "cm-3") is None

    async def test_find_completed_turn_failed_excluded(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id="cm-4")
        await conv.finalize_turn(tid, "failed", error_code="X")
        assert await conv.find_completed_turn(cid, "cm-4") is None

    async def test_find_completed_turn_missing_cmid(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.find_completed_turn(cid, "no-such") is None


class TestGetTurnAssistantTexts:
    """取某 user 回合后、下一个 user 回合前的所有 assistant content。"""

    async def test_single_turn_collects_assistant(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "q", client_message_id="cm-1")
        await conv.finalize_turn(tid, "done")
        await conv.append_message(cid, "assistant", "a1")
        await conv.append_message(cid, "assistant", "a2")
        texts = await conv.get_turn_assistant_texts(cid, tid)
        assert texts == ["a1", "a2"]

    async def test_stops_at_next_user_row(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        t1 = await conv.append_user_turn(cid, "q1", client_message_id="cm-1")
        await conv.finalize_turn(t1, "done")
        await conv.append_message(cid, "assistant", "a1")
        # 第二个 user 之后的 assistant 不应被收录
        await conv.append_user_turn(cid, "q2", client_message_id="cm-2")
        await conv.append_message(cid, "assistant", "a2")
        texts = await conv.get_turn_assistant_texts(cid, t1)
        assert texts == ["a1"]

    async def test_no_assistant_returns_empty(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "q", client_message_id="cm-1")
        await conv.finalize_turn(tid, "done")
        assert await conv.get_turn_assistant_texts(cid, tid) == []


class TestCountPendingAndArchive:
    async def test_count_pending_zero(self, db_ready) -> None:
        assert await conv.count_pending() == 0

    async def test_count_pending_after_set_mode(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await conv.set_mode(c1, "human_pending")
        await conv.set_mode(c2, "human_pending")
        await conv.create_conversation("c", "U3")  # ai 不算
        assert await conv.count_pending() == 2

    async def test_archive_blocks_resumable(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.archive_conversation(cid)
        assert await conv.get_resumable(cid, "c", "U1") is None

    async def test_mark_needs_review(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.mark_needs_review(cid)
        meta = await conv.get_meta_with_risk(cid)
        assert meta is not None and meta["needs_review"] == 1


class TestCountUserTurnsAndChars:
    async def test_zero_when_empty(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.count_user_turns(cid) == 0
        assert await conv.sum_content_chars(cid) == 0

    async def test_counts_only_user(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_user_turn(cid, "a", client_message_id=None)
        await conv.append_message(cid, "assistant", "b")
        await conv.append_user_turn(cid, "c", client_message_id=None)
        assert await conv.count_user_turns(cid) == 2

    async def test_chars_sums_all_roles(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_user_turn(cid, "ab", client_message_id=None)  # 2
        await conv.append_message(cid, "assistant", "xyz")  # 3
        assert await conv.sum_content_chars(cid) == 5


class TestListMessagesAndPagination:
    async def test_list_messages_ordered_by_id(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_user_turn(cid, "q1", client_message_id=None)
        await conv.append_message(cid, "assistant", "a1")
        await conv.append_user_turn(cid, "q2", client_message_id=None)
        rows = await conv.list_messages(cid)
        assert [r["content"] for r in rows] == ["q1", "a1", "q2"]

    async def test_list_messages_page_latest_n(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        for i in range(5):
            await conv.append_message(cid, "user", f"m{i}")
        rows = await conv.list_messages_page(cid, limit=2)
        # 升序返回，但只最新 2 条
        assert [r["content"] for r in rows] == ["m3", "m4"]

    async def test_list_messages_page_before_id(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        ids = []
        for i in range(5):
            ids.append(await conv.append_message(cid, "user", f"m{i}"))
        rows = await conv.list_messages_page(cid, limit=2, before_id=ids[3])
        assert [r["content"] for r in rows] == ["m1", "m2"]

    async def test_list_recent_messages(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        for i in range(4):
            await conv.append_message(cid, "user", f"m{i}")
        rows = await conv.list_recent_messages(cid, limit=3)
        assert [r["content"] for r in rows] == ["m1", "m2", "m3"]

    async def test_list_empty_returns_empty(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.list_messages(cid) == []
        assert await conv.list_messages_page(cid, limit=10) == []


class TestSetModeAndGetMode:
    @pytest.mark.parametrize("mode", ["ai", "human_pending", "human_takeover", "ai_draft"])
    async def test_valid_modes(self, db_ready, mode: str) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, mode)
        got_mode, _ = await conv.get_mode(cid)
        assert got_mode == mode

    async def test_invalid_mode_raises(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        with pytest.raises(ValueError):
            await conv.set_mode(cid, "invalid")

    async def test_human_takeover_records_assigned(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="staff-1")
        _, sid = await conv.get_mode(cid)
        assert sid == "staff-1"
        meta = await conv.get_conversation_meta(cid)
        assert meta is not None
        assert meta["assigned_staff_id"] == "staff-1"

    async def test_non_takeover_does_not_overwrite_assigned_at(self, db_ready) -> None:
        """SET ... CASE WHEN takeover=0 THEN assigned_at ELSE :at：非接管不重写。"""
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="s1")
        meta1 = await conv.get_meta_with_risk(cid)
        await asyncio.sleep(0.01)
        await conv.set_mode(cid, "ai")  # 释放回 AI
        meta2 = await conv.get_meta_with_risk(cid)
        # assigned_at 不被擦除
        assert meta1 is not None and meta2 is not None
        assert meta1["assigned_at"] == meta2["assigned_at"]

    async def test_get_mode_missing_raises(self, db_ready) -> None:
        with pytest.raises(ValueError):
            await conv.get_mode(99999)


class TestGetMetaWithRisk:
    """get_meta_with_risk：基础元 + 4 项风险信号。"""

    async def test_no_risk_flags_when_clean(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        meta = await conv.get_meta_with_risk(cid)
        assert meta is not None
        # SQLite EXISTS 返回 0/1
        assert int(meta["has_failed"]) == 0
        assert int(meta["has_out_of_scope"]) == 0
        assert int(meta["has_downvote"]) == 0
        assert int(meta["has_empty_tool"]) == 0

    async def test_has_failed_flag(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id=None)
        await conv.finalize_turn(tid, "failed", error_code="X")
        meta = await conv.get_meta_with_risk(cid)
        assert meta is not None
        assert int(meta["has_failed"]) == 1

    async def test_has_out_of_scope_flag(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id=None)
        await conv.finalize_turn(tid, "done")
        await conv.set_turn_verdict(tid, "no")
        meta = await conv.get_meta_with_risk(cid)
        assert meta is not None
        assert int(meta["has_out_of_scope"]) == 1


class TestListForStaff:
    async def test_default_excludes_ai_mode(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")  # 默认 ai
        c2 = await conv.create_conversation("c", "U2")
        await conv.set_mode(c2, "human_pending")
        rows = await conv.list_for_staff()
        ids = {r["id"] for r in rows}
        assert c2 in ids
        assert c1 not in ids  # ai 默认被排除

    async def test_filter_status_human_pending(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await conv.set_mode(c1, "human_pending")
        await conv.set_mode(c2, "human_takeover", assigned_staff_id="s1")
        rows = await conv.list_for_staff(filter_status="human_pending")
        ids = {r["id"] for r in rows}
        assert c1 in ids and c2 not in ids

    async def test_risk_only_includes_ai_mode_with_failed_turn(self, db_ready) -> None:
        """risk_only=True 不受 mode 限制，仅风险信号筛。"""
        c_ai = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(c_ai, "x", client_message_id=None)
        await conv.finalize_turn(tid, "failed", error_code="X")
        c_clean = await conv.create_conversation("c", "U2")
        rows = await conv.list_for_staff(risk_only=True)
        ids = {r["id"] for r in rows}
        assert c_ai in ids
        assert c_clean not in ids

    async def test_risk_only_includes_needs_review(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.mark_needs_review(cid)
        rows = await conv.list_for_staff(risk_only=True)
        assert cid in {r["id"] for r in rows}


class TestAiDrafts:
    async def test_save_get_clear_draft(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        assert await conv.get_latest_ai_draft(cid) is None
        await conv.save_ai_draft(cid, "draft-1")
        await conv.save_ai_draft(cid, "draft-2")
        assert await conv.get_latest_ai_draft(cid) == "draft-2"
        await conv.clear_ai_drafts(cid)
        assert await conv.get_latest_ai_draft(cid) is None


class TestAppendHumanMessage:
    async def test_human_message_role_and_sender(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        mid = await conv.append_human_message(cid, "staff-1", "您好")
        rows = await conv.list_messages(cid)
        assert len(rows) == 1 and rows[0]["id"] == mid
        assert rows[0]["role"] == "human_agent"
        assert rows[0]["sender_staff_id"] == "staff-1"
        assert rows[0]["content"] == "您好"


class TestSqlitePostgresTypeAmbiguity:
    """user memory `sqlite-vs-postgres-test-gap`: CAST(:p AS TEXT) 形 SQL 在 SQLite 跑通即可。"""

    async def test_list_messages_page_before_id_none(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_message(cid, "user", "m")
        rows = await conv.list_messages_page(cid, limit=10, before_id=None)
        assert len(rows) == 1
