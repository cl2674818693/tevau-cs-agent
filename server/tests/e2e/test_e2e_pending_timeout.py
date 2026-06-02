"""E2E 剧本 #11：转人工后长时间无人接 → sweep 兜底推事项中心。

剧本梗概：
    1. 配置 sla_policies: metric=take_time, threshold_seconds=10。
    2. 用户求人工 → human_pending；伪造 conversation.created_at 落在阈值之外（超时）。
    3. 调 push_pending_takeover_timeouts() →
         - 事项中心 inbox 收到 type=pending_takeover_timeout payload；
         - pending_timeout_pushes 表写入去重记录。
    4. 再次调 push_pending_takeover_timeouts() → 已去重，inbox 不再追加。
    5. 已接管的会话不再触发 takeover SLA（take 记录存在 → take_time 不算违规）。

异常分支：
    - push 失败（push_event_center 返回 False）→ pending_timeout_pushes 不写，下次仍会重试。
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import admin_sla
from ai_engine.persistence import db as db_mod
from ai_engine.persistence import maintenance as mt


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    """建会话并立即求人工。"""
    r = await c_client.post("/api/v1/conversations", json={})
    cid = int(r.json()["conversation_id"])
    await c_client.post(
        f"/api/v1/conversations/{cid}/request-human", json={"reason": "x"}
    )
    return cid


async def _make_conv_old(conv_id: int, seconds_old: int) -> None:
    """把 conversations.created_at 调到过去，模拟"建会话已 N 秒"。"""
    past = (datetime.now(UTC) - timedelta(seconds=seconds_old)).strftime("%Y-%m-%d %H:%M:%S")
    await db_mod.execute(
        "UPDATE conversations SET created_at=:p WHERE id=:id",
        {"p": past, "id": conv_id},
    )


async def _create_sla(metric: str, threshold: int) -> None:
    await admin_sla.create_policy(metric, threshold, "all", None)


class TestPendingTimeout:
    async def test_sweep_pushes_pending_timeout_event(
        self,
        conv_id: int,
        _mock_event_center: list[dict[str, Any]],
    ) -> None:
        """新建会话超 SLA 阈值未接管 → push pending_takeover_timeout。"""
        await _create_sla("take_time", 10)
        await _make_conv_old(conv_id, seconds_old=120)
        _mock_event_center.clear()

        pushed = await mt.push_pending_takeover_timeouts()
        assert pushed == 1

        pushes = [it["push"] for it in _mock_event_center if "push" in it]
        timeouts = [p for p in pushes if p.get("type") == "pending_takeover_timeout"]
        assert len(timeouts) == 1
        assert timeouts[0]["conversation_id"] == conv_id
        assert timeouts[0]["threshold_seconds"] == 10
        assert timeouts[0]["elapsed_seconds"] >= 120

        # 去重表已写
        row = await db_mod.fetch_one(
            "SELECT conversation_id FROM pending_timeout_pushes WHERE conversation_id=:id",
            {"id": conv_id},
        )
        assert row is not None

    async def test_sweep_dedup_does_not_double_push(
        self,
        conv_id: int,
        _mock_event_center: list[dict[str, Any]],
    ) -> None:
        """同会话 sweep 两次 → 第二次不会再推。"""
        await _create_sla("take_time", 10)
        await _make_conv_old(conv_id, seconds_old=120)

        await mt.push_pending_takeover_timeouts()
        _mock_event_center.clear()
        again = await mt.push_pending_takeover_timeouts()
        assert again == 0
        assert not [it for it in _mock_event_center if "push" in it]

    async def test_taken_conversation_not_in_breaches(
        self,
        conv_id: int,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """会话已被 take → take_time 不再算违规（compute_breaches 不返回它）。"""
        await _create_sla("take_time", 10)
        await _make_conv_old(conv_id, seconds_old=120)

        sc = make_staff_client(seeded_agent, "agent")
        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r.status_code == 200

        breaches = await admin_sla.compute_breaches()
        take_for_us = [
            b
            for b in breaches
            if b["conversation_id"] == conv_id and b["metric"] == "take_time"
        ]
        assert not take_for_us

    async def test_no_sla_policy_skips_sweep(
        self,
        conv_id: int,
        _mock_event_center: list[dict[str, Any]],
    ) -> None:
        """未配 SLA 策略 → sweep 直接 0 不推。"""
        await _make_conv_old(conv_id, seconds_old=120)
        n = await mt.push_pending_takeover_timeouts()
        assert n == 0

    async def test_push_failure_does_not_mark_dedup(
        self,
        conv_id: int,
        monkeypatch,
    ) -> None:
        """push_event_center 失败 → 去重表不写，下次仍会重试。"""
        await _create_sla("take_time", 10)
        await _make_conv_old(conv_id, seconds_old=120)

        async def _fail_push(payload):
            return False

        monkeypatch.setattr(mt, "push_event_center", _fail_push)
        pushed = await mt.push_pending_takeover_timeouts()
        assert pushed == 0
        row = await db_mod.fetch_one(
            "SELECT conversation_id FROM pending_timeout_pushes WHERE conversation_id=:id",
            {"id": conv_id},
        )
        assert row is None

    async def test_reclaim_stale_turns_marks_processing_as_failed(
        self, c_client: AsyncClient
    ) -> None:
        """processing 卡太久 → reclaim_stale_turns 标 failed + error_code=STALE_RECLAIMED。"""
        r = await c_client.post("/api/v1/conversations", json={})
        cid = int(r.json()["conversation_id"])
        # 落一条 processing 的 user 行，created_at 调到很久前
        past = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await db_mod.execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', :c, 'processing', :p)",
            {"cid": cid, "c": "卡住的提问", "p": past},
        )

        n = await mt.reclaim_stale_turns(timeout_seconds=120)
        assert n == 1
        row = await db_mod.fetch_one(
            "SELECT status, error_code FROM messages WHERE conversation_id=:cid",
            {"cid": cid},
        )
        assert row["status"] == "failed"
        assert row["error_code"] == "STALE_RECLAIMED"
