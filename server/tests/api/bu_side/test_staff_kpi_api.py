"""API: GET /staff/api/v1/kpi（staff_kpi.py）。

被测对象：客服 KPI 看板 = per-staff 绩效 + 全局 AI 质量指标。
策略：直接 INSERT staff_actions + 各种 conversations/messages/feedback/tool_audits，
让 compute_kpi / ai_quality 真实聚合。

异常矩阵：
1. 未登录 → 401
2. happy path：单客服 take→resolved 流程 → KPI 正确
3. 时间窗口过滤：date_from/date_to 排除窗口外动作
4. 全局 AI 质量：handoff_rate / downvote_rate / tool_empty_rate 正确
5. 空数据：返回 0 不抛除零
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_kpi import router as staff_kpi_router
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.schema import now_str

from .conftest import insert_conversation, insert_message


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_kpi_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _insert_action(
    cid: int, sid: str, action: str, at: str | None = None
) -> None:
    await db_mod.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:c, :s, :a, :at)",
        {"c": cid, "s": sid, "a": action, "at": at or now_str()},
    )


class TestKpiAuth:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/kpi")
        assert resp.status_code == 401


class TestKpiHappyPath:
    async def test_empty_state_returns_empty_lists_and_zeros(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["staff"] == []
        quality = body["ai_quality"]
        assert quality["total_conversations"] == 0
        assert quality["handoff_rate"] == 0.0
        assert quality["downvote_rate"] == 0.0
        assert quality["tool_empty_rate"] == 0.0

    async def test_single_staff_take_resolved(
        self, init_self_db, client, agent_headers
    ) -> None:
        """agent-1 take 一个会话然后 resolved：takeovers=1, resolved=1, resolved_ratio=1.0。"""
        cid = await insert_conversation(mode="ai")
        t0 = (datetime.now(UTC) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        await _insert_action(cid, "agent-1", "take", at=t0)
        await _insert_action(cid, "agent-1", "resolved", at=now_str())

        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        assert resp.status_code == 200
        rows = resp.json()["staff"]
        assert len(rows) == 1
        r = rows[0]
        assert r["staff_id"] == "agent-1"
        assert r["takeovers"] == 1
        assert r["resolved"] == 1
        assert r["releases"] == 0
        assert r["resolved_ratio"] == 1.0
        assert r["release_ratio"] == 0.0
        # 平均接管时长大约 5 分钟 = 300s（允许 ±30s 误差）
        assert 270 <= r["avg_handle_seconds"] <= 330

    async def test_mixed_actions_aggregated(
        self, init_self_db, client, agent_headers
    ) -> None:
        c1 = await insert_conversation()
        c2 = await insert_conversation()
        c3 = await insert_conversation()
        # take + release
        await _insert_action(c1, "agent-1", "take")
        await _insert_action(c1, "agent-1", "release")
        # take + resolved
        await _insert_action(c2, "agent-1", "take")
        await _insert_action(c2, "agent-1", "resolved")
        # take + transfer_out
        await _insert_action(c3, "agent-1", "take")
        await _insert_action(c3, "agent-1", "transfer_out")

        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        r = next(s for s in resp.json()["staff"] if s["staff_id"] == "agent-1")
        assert r["takeovers"] == 3
        assert r["releases"] == 1
        assert r["resolved"] == 1
        assert r["transfers"] == 1
        # 口径：分母 = releases + resolved = 2
        assert r["resolved_ratio"] == 0.5
        assert r["release_ratio"] == 0.5
        # transfer_ratio = transfers / takeovers
        assert r["transfer_ratio"] == round(1 / 3, 3)


class TestKpiDateRangeFilter:
    async def test_date_window_excludes_old(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        # 一条很旧的动作：2025-01-01
        await _insert_action(cid, "agent-1", "take", at="2025-01-01 00:00:00")
        # 一条今天的：take + resolved
        await _insert_action(cid, "agent-2", "take", at=now_str())
        await _insert_action(cid, "agent-2", "resolved", at=now_str())

        # 用 from=2026-01-01 排除老的
        resp = await client.get(
            "/staff/api/v1/kpi?from=2026-01-01", headers=agent_headers
        )
        assert resp.status_code == 200
        rows = resp.json()["staff"]
        ids = {r["staff_id"] for r in rows}
        assert ids == {"agent-2"}


class TestKpiAiQuality:
    async def test_handoff_rate_computed(
        self, init_self_db, client, agent_headers
    ) -> None:
        await insert_conversation(mode="ai")
        await insert_conversation(mode="human_pending")
        await insert_conversation(mode="human_takeover")
        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        q = resp.json()["ai_quality"]
        assert q["total_conversations"] == 3
        assert q["handoff"] == 2
        assert q["handoff_rate"] == pytest.approx(2 / 3)

    async def test_tool_empty_rate(
        self, init_self_db, client, agent_headers
    ) -> None:
        from ai_engine.persistence import audit as audit_dao

        cid = await insert_conversation()
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None, is_empty=False,
        )
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None, is_empty=True,
        )
        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        q = resp.json()["ai_quality"]
        assert q["tool_calls"] == 2
        assert q["tool_empty"] == 1
        assert q["tool_empty_rate"] == 0.5

    async def test_downvote_rate(
        self, init_self_db, client, agent_headers
    ) -> None:
        from ai_engine.persistence import feedback as fb_dao

        cid = await insert_conversation(user_type="c", subject_id="U")
        mid = await insert_message(cid, role="assistant", content="x")
        await fb_dao.add_feedback(cid, mid, "up", None, "U", "c")
        await fb_dao.add_feedback(cid, mid, "down", None, "U", "c")
        await fb_dao.add_feedback(cid, mid, "down", None, "U", "c")

        resp = await client.get("/staff/api/v1/kpi", headers=agent_headers)
        q = resp.json()["ai_quality"]
        assert q["upvote"] == 1
        assert q["downvote"] == 2
        assert q["downvote_rate"] == pytest.approx(2 / 3)
