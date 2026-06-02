"""Persistence: shifts_query.py — is_on_shift helper。

覆盖：当前时间 / 指定时间 / 无班次 / 时间窗外。
"""

from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import admin_shifts, shifts_query
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestIsOnShift:
    async def test_no_shifts_returns_false(self, db_ready) -> None:
        assert await shifts_query.is_on_shift("s1") is False

    async def test_within_current_shift(self, db_ready) -> None:
        start = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        await admin_shifts.create_shift("s1", start, end)
        assert await shifts_query.is_on_shift("s1") is True

    async def test_outside_shift(self, db_ready) -> None:
        # 班次已结束
        start = (datetime.now(UTC) - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        end = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        await admin_shifts.create_shift("s1", start, end)
        assert await shifts_query.is_on_shift("s1") is False

    async def test_other_staff_unaffected(self, db_ready) -> None:
        start = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        await admin_shifts.create_shift("s1", start, end)
        assert await shifts_query.is_on_shift("s2") is False

    async def test_explicit_when(self, db_ready) -> None:
        await admin_shifts.create_shift(
            "s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00"
        )
        # 在班
        assert await shifts_query.is_on_shift("s1", when="2026-01-01 12:00:00") is True
        # 不在班
        assert await shifts_query.is_on_shift("s1", when="2026-01-02 09:00:00") is False
