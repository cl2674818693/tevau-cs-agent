"""F-P0-4 / B-P1 客服心跳超时 → 自动释放接管。

防客服掉线后 mode=human_takeover 卡死，用户等不到回复也没人能接手。
"""

from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import conversations as conv
from ai_engine.persistence import maintenance, staff_presence
from ai_engine.persistence.db import execute, fetch_one


@pytest.fixture
async def db_ready(seeded_db):
    return seeded_db


class TestReclaimZombieTakeovers:
    async def test_releases_conv_assigned_to_offline_staff(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U-1")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="agent-1")
        # 心跳很久之前
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO staff_presence(staff_id, status, last_seen_at) "
            "VALUES (:sid, 'online', :old)",
            {"sid": "agent-1", "old": old},
        )
        released = await maintenance.reclaim_zombie_takeovers(staff_idle_seconds=300)
        assert cid in released
        row = await fetch_one(
            "SELECT mode, assigned_staff_id FROM conversations WHERE id=:id", {"id": cid}
        )
        assert row["mode"] == "ai"
        assert row["assigned_staff_id"] is None

    async def test_keeps_conv_when_staff_still_alive(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U-2")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="agent-2")
        await staff_presence.heartbeat("agent-2", "online")
        released = await maintenance.reclaim_zombie_takeovers(staff_idle_seconds=300)
        assert cid not in released
        row = await fetch_one(
            "SELECT mode, assigned_staff_id FROM conversations WHERE id=:id", {"id": cid}
        )
        assert row["mode"] == "human_takeover"
        assert row["assigned_staff_id"] == "agent-2"

    async def test_skips_conv_without_presence_record(self, db_ready) -> None:
        """staff 从未发心跳（无 presence 行）→ 视为离线，立刻释放。"""
        cid = await conv.create_conversation("c", "U-3")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="ghost-staff")
        released = await maintenance.reclaim_zombie_takeovers(staff_idle_seconds=300)
        assert cid in released
