"""Persistence: staff_metrics.py — 客服动作埋点 + KPI 聚合 + AI 全局质量。

覆盖：log_staff_action（含 take→release/resolved/transfer_out 配对）,
compute_kpi（口径修正：分母 release+resolved，transfer 单列）,
ai_quality（转人工率/差评率/工具空结果率，防除零）,
refresh_human_pending（gauge 与 DB 一致）。
"""

import asyncio

import pytest

from ai_engine.persistence import conversations as conv
from ai_engine.persistence import staff_metrics as sm
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestLogStaffActionAndKPI:
    async def test_log_and_aggregate_take_release(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(cid, "s1", "take")
        await sm.log_staff_action(cid, "s1", "release")
        kpis = await sm.compute_kpi(None, None)
        assert len(kpis) == 1
        k = kpis[0]
        assert k["staff_id"] == "s1"
        assert k["takeovers"] == 1
        assert k["releases"] == 1
        assert k["resolved"] == 0
        assert k["transfers"] == 0
        assert k["release_ratio"] == 1.0  # 1/(1+0)
        assert k["resolved_ratio"] == 0.0

    async def test_resolve_ratio_correct(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await sm.log_staff_action(c1, "s1", "take")
        await sm.log_staff_action(c1, "s1", "resolved")
        await sm.log_staff_action(c2, "s1", "take")
        await sm.log_staff_action(c2, "s1", "release")
        kpis = await sm.compute_kpi(None, None)
        k = kpis[0]
        # base = 1+1=2; resolved/base = 1/2 = 0.5
        assert k["resolved_ratio"] == 0.5
        assert k["release_ratio"] == 0.5

    async def test_transfer_ratio_separate(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(c1, "s1", "take")
        await sm.log_staff_action(c1, "s1", "transfer_out")
        kpis = await sm.compute_kpi(None, None)
        k = kpis[0]
        # transfer_out 不入 base 分母（资源/解决比率 base=0 → 0.0）
        assert k["release_ratio"] == 0.0
        assert k["resolved_ratio"] == 0.0
        # transfer_ratio = transfers/takeovers = 1/1
        assert k["transfer_ratio"] == 1.0

    async def test_avg_handle_seconds(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(cid, "s1", "take")
        await asyncio.sleep(1.1)  # 跨秒：handle_seconds ≥ 1
        await sm.log_staff_action(cid, "s1", "release")
        kpis = await sm.compute_kpi(None, None)
        assert kpis[0]["avg_handle_seconds"] >= 1.0

    async def test_no_actions_empty_list(self, db_ready) -> None:
        assert await sm.compute_kpi(None, None) == []

    async def test_date_filter(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(cid, "s1", "take")
        # 过去时间窗：拿不到
        kpis = await sm.compute_kpi("1900-01-01 00:00:00", "1900-01-02 00:00:00")
        assert kpis == []

    async def test_multiple_staff_sorted(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(cid, "bob", "take")
        await sm.log_staff_action(cid, "bob", "release")
        c2 = await conv.create_conversation("c", "U2")
        await sm.log_staff_action(c2, "alice", "take")
        await sm.log_staff_action(c2, "alice", "release")
        kpis = await sm.compute_kpi(None, None)
        assert [k["staff_id"] for k in kpis] == ["alice", "bob"]  # 按 staff_id 排序

    async def test_release_without_prior_take(self, db_ready) -> None:
        """end 动作没匹配的 take：handle_seconds 空，比率仍正常算。"""
        cid = await conv.create_conversation("c", "U1")
        await sm.log_staff_action(cid, "s1", "release")
        kpis = await sm.compute_kpi(None, None)
        assert kpis[0]["takeovers"] == 0
        assert kpis[0]["releases"] == 1
        assert kpis[0]["avg_handle_seconds"] == 0.0


class TestRefreshHumanPending:
    async def test_runs_without_error(self, db_ready) -> None:
        """gauge 刷新只需 DB 调通；metrics 副作用此处不验证。"""
        await sm.refresh_human_pending()
        c1 = await conv.create_conversation("c", "U1")
        await conv.set_mode(c1, "human_pending")
        await sm.refresh_human_pending()


class TestAIQuality:
    async def test_zero_state_returns_zeros(self, db_ready) -> None:
        m = await sm.ai_quality(None, None)
        assert m["total_conversations"] == 0
        assert m["handoff"] == 0
        assert m["handoff_rate"] == 0.0
        assert m["downvote_rate"] == 0.0
        assert m["tool_empty_rate"] == 0.0

    async def test_handoff_rate(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        await conv.create_conversation("c", "U2")
        await conv.set_mode(c1, "human_pending")
        m = await sm.ai_quality(None, None)
        assert m["total_conversations"] == 2
        assert m["handoff"] == 1
        assert m["handoff_rate"] == 0.5

    async def test_downvote_rate(self, db_ready) -> None:
        from ai_engine.persistence import feedback as fb

        cid = await conv.create_conversation("c", "U1")
        mid = await conv.append_message(cid, "assistant", "ans")
        await fb.add_feedback(cid, mid, "up", None, "U1", "c")
        await fb.add_feedback(cid, mid, "down", "bad", "U1", "c")
        m = await sm.ai_quality(None, None)
        assert m["upvote"] == 1
        assert m["downvote"] == 1
        assert m["downvote_rate"] == 0.5

    async def test_tool_empty_rate(self, db_ready) -> None:
        from ai_engine.persistence import audit

        cid = await conv.create_conversation("c", "U1")
        await audit.log_tool_call(cid, "t", {}, 0, 1, False, None, result_count=0, is_empty=True)
        await audit.log_tool_call(cid, "t", {}, 0, 1, False, None, result_count=1, is_empty=False)
        m = await sm.ai_quality(None, None)
        assert m["tool_calls"] == 2
        assert m["tool_empty"] == 1
        assert m["tool_empty_rate"] == 0.5

    async def test_out_of_scope_and_failed_turns(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id=None)
        await conv.finalize_turn(tid, "failed", error_code="X")
        tid2 = await conv.append_user_turn(cid, "y", client_message_id=None)
        await conv.finalize_turn(tid2, "done")
        await conv.set_turn_verdict(tid2, "no")
        m = await sm.ai_quality(None, None)
        assert m["failed_turns"] == 1
        assert m["out_of_scope"] == 1

    async def test_date_range_filter(self, db_ready) -> None:
        await conv.create_conversation("c", "U1")
        # 过去窗口 → 全为 0
        m = await sm.ai_quality("1900-01-01 00:00:00", "1900-01-02 00:00:00")
        assert m["total_conversations"] == 0

    async def test_uses_cast_text_idiom_for_postgres(self, db_ready) -> None:
        """SQL 中 (CAST(:p AS TEXT) IS NULL OR ...) 形式：None 参数下不应抛类型歧义。"""
        # 隐式：上面的 zero_state / date_range 已覆盖 None 与字符串两路径
        now = now_str()
        m = await sm.ai_quality(now, now)
        assert isinstance(m["total_conversations"], int)
