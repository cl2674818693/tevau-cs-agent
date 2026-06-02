"""Persistence: admin_shifts.py — 排班 CRUD + 时间范围查询。

覆盖：create_shift / list_shifts(过滤 staff_id / 时间窗 / limit) /
patch_shift（部分字段 / no updatable raise / 不存在返回 None） / delete_shift。
"""

import pytest

from ai_engine.persistence import admin_shifts as sh
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestCreateShift:
    async def test_create_returns_pk(self, db_ready) -> None:
        sid = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        assert sid > 0

    async def test_overlapping_allowed(self, db_ready) -> None:
        """schema 无 UNIQUE 约束，重叠应当允许（业务上同人多班次场景）。"""
        a = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 12:00:00")
        b = await sh.create_shift("s1", "2026-01-01 11:00:00", "2026-01-01 14:00:00")
        assert a != b


class TestListShifts:
    async def test_no_filter(self, db_ready) -> None:
        await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        await sh.create_shift("s2", "2026-01-02 09:00:00", "2026-01-02 18:00:00")
        rows = await sh.list_shifts()
        assert len(rows) == 2

    async def test_filter_by_staff(self, db_ready) -> None:
        await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        await sh.create_shift("s2", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        rows = await sh.list_shifts(staff_id="s2")
        assert [r["staff_id"] for r in rows] == ["s2"]

    async def test_filter_by_date_window(self, db_ready) -> None:
        await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        await sh.create_shift("s1", "2026-02-01 09:00:00", "2026-02-01 18:00:00")
        rows = await sh.list_shifts(
            date_from="2026-01-15 00:00:00", date_to="2026-12-31 23:59:59"
        )
        # 仅 2026-02 那条在窗口
        assert len(rows) == 1
        assert rows[0]["start_at"].startswith("2026-02")

    async def test_limit(self, db_ready) -> None:
        for i in range(5):
            await sh.create_shift("s1", f"2026-01-0{i + 1} 09:00:00", f"2026-01-0{i + 1} 18:00:00")
        rows = await sh.list_shifts(limit=3)
        assert len(rows) == 3

    async def test_ordered_by_start(self, db_ready) -> None:
        await sh.create_shift("s1", "2026-03-01 09:00:00", "2026-03-01 18:00:00")
        await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        rows = await sh.list_shifts()
        assert rows[0]["start_at"] < rows[1]["start_at"]

    async def test_empty(self, db_ready) -> None:
        assert await sh.list_shifts() == []


class TestPatchShift:
    async def test_partial_update(self, db_ready) -> None:
        sid = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        row = await sh.patch_shift(sid, {"end_at": "2026-01-01 20:00:00"})
        assert row is not None
        assert row["end_at"] == "2026-01-01 20:00:00"
        assert row["start_at"] == "2026-01-01 09:00:00"  # 不变

    async def test_unknown_keys_ignored(self, db_ready) -> None:
        """非白名单字段被丢掉，但有合法字段就能更新。"""
        sid = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        row = await sh.patch_shift(sid, {"end_at": "2026-01-01 20:00:00", "garbage": "x"})
        assert row is not None and row["end_at"] == "2026-01-01 20:00:00"

    async def test_no_updatable_raises(self, db_ready) -> None:
        sid = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        with pytest.raises(ValueError):
            await sh.patch_shift(sid, {"garbage": "x"})

    async def test_missing_returns_none(self, db_ready) -> None:
        row = await sh.patch_shift(99999, {"end_at": "2026-01-01 20:00:00"})
        assert row is None


class TestDeleteShift:
    async def test_delete(self, db_ready) -> None:
        sid = await sh.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        await sh.delete_shift(sid)
        assert await sh.list_shifts() == []

    async def test_delete_missing_no_error(self, db_ready) -> None:
        await sh.delete_shift(99999)
