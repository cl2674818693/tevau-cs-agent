"""Persistence: staff_presence.py — 心跳 upsert + 在线列表。

覆盖：heartbeat(upsert) / set_offline / list_all / list_active(window)。
SQLite 的 ON CONFLICT 与 Postgres 通用。
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import staff_presence
from ai_engine.persistence.db import execute, init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestHeartbeat:
    async def test_upsert_inserts_then_updates(self, db_ready) -> None:
        await staff_presence.heartbeat("s1", status="online")
        rows = await staff_presence.list_all()
        assert len(rows) == 1
        assert rows[0]["status"] == "online"
        first_seen = rows[0]["last_seen_at"]
        # 第二次 heartbeat：upsert 不复制行
        await asyncio.sleep(1.05)
        await staff_presence.heartbeat("s1", status="away")
        rows = await staff_presence.list_all()
        assert len(rows) == 1
        assert rows[0]["status"] == "away"
        assert rows[0]["last_seen_at"] >= first_seen

    async def test_default_status_online(self, db_ready) -> None:
        await staff_presence.heartbeat("s1")
        rows = await staff_presence.list_all()
        assert rows[0]["status"] == "online"


class TestSetOffline:
    async def test_marks_offline(self, db_ready) -> None:
        await staff_presence.heartbeat("s1", "online")
        await staff_presence.set_offline("s1")
        rows = await staff_presence.list_all()
        assert rows[0]["status"] == "offline"

    async def test_no_row_no_error(self, db_ready) -> None:
        await staff_presence.set_offline("ghost")


class TestListAll:
    async def test_ordered_by_staff_id(self, db_ready) -> None:
        for sid in ("zoe", "alice", "bob"):
            await staff_presence.heartbeat(sid)
        rows = await staff_presence.list_all()
        assert [r["staff_id"] for r in rows] == ["alice", "bob", "zoe"]

    async def test_empty(self, db_ready) -> None:
        assert await staff_presence.list_all() == []


class TestListActive:
    async def test_excludes_offline(self, db_ready) -> None:
        await staff_presence.heartbeat("s1", "online")
        await staff_presence.heartbeat("s2", "online")
        await staff_presence.set_offline("s1")
        rows = await staff_presence.list_active()
        ids = {r["staff_id"] for r in rows}
        assert ids == {"s2"}

    async def test_window_filter(self, db_ready) -> None:
        """last_seen_at 早于 cutoff 应被过滤。手工写一个老时间戳。"""
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO staff_presence(staff_id, status, last_seen_at) VALUES (:s, :st, :t)",
            {"s": "old", "st": "online", "t": old},
        )
        await staff_presence.heartbeat("fresh", "online")
        rows = await staff_presence.list_active(window_seconds=300)
        ids = {r["staff_id"] for r in rows}
        assert "fresh" in ids and "old" not in ids

