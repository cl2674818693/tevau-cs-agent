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


class TestAnyOnShift:
    """any_on_shift：只要有一位客服在班就返回 True，转人工入口用。"""

    async def test_empty_shifts_returns_false(self, db_ready) -> None:
        assert await shifts_query.any_on_shift() is False

    async def test_one_staff_on_shift(self, db_ready) -> None:
        start = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end = (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        await admin_shifts.create_shift("s1", start, end)
        assert await shifts_query.any_on_shift() is True

    async def test_all_shifts_ended_returns_false(self, db_ready) -> None:
        # 全部班次已结束 = 班外
        s = (datetime.now(UTC) - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        e = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        await admin_shifts.create_shift("s1", s, e)
        await admin_shifts.create_shift("s2", s, e)
        assert await shifts_query.any_on_shift() is False

    async def test_multi_staff_only_one_in_shift(self, db_ready) -> None:
        # s1 在班，s2 不在 → any_on_shift True
        now = datetime.now(UTC)
        await admin_shifts.create_shift(
            "s1",
            (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
        )
        await admin_shifts.create_shift(
            "s2",
            (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
            (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
        )
        assert await shifts_query.any_on_shift() is True

    async def test_explicit_when_off_hours(self, db_ready) -> None:
        # 排班 09:00-18:00，凌晨 03:00 查 → 班外
        await admin_shifts.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        assert await shifts_query.any_on_shift(when="2026-01-01 03:00:00") is False
        assert await shifts_query.any_on_shift(when="2026-01-01 12:00:00") is True


class TestNextShiftStart:
    """next_shift_start：返回不早于 when 的最近一次 shift 开始时间，没有就 None。"""

    async def test_no_future_shift_returns_none(self, db_ready) -> None:
        assert await shifts_query.next_shift_start() is None

    async def test_returns_earliest_future_shift_iso_with_z(self, db_ready) -> None:
        # 两个未来班次，应返回最早的；输出必须是 ISO 8601 with Z（防跨时区用户误判）
        await admin_shifts.create_shift("s1", "2026-06-04 09:00:00", "2026-06-04 18:00:00")
        await admin_shifts.create_shift("s2", "2026-06-03 21:00:00", "2026-06-04 03:00:00")
        nxt = await shifts_query.next_shift_start(when="2026-06-03 12:00:00")
        # 关键：返回 ISO 8601 with Z 而非裸的 "2026-06-03 21:00:00"
        assert nxt == "2026-06-03T21:00:00Z"

    async def test_past_shifts_ignored(self, db_ready) -> None:
        # 排班全在过去 → None
        await admin_shifts.create_shift("s1", "2026-01-01 09:00:00", "2026-01-01 18:00:00")
        nxt = await shifts_query.next_shift_start(when="2026-06-01 12:00:00")
        assert nxt is None

    async def test_current_shift_returns_next_not_self(self, db_ready) -> None:
        # 当前 12:00 在 09:00-18:00 班次中：返回下一段 21:00 的班，不是本班次
        await admin_shifts.create_shift("s1", "2026-06-03 09:00:00", "2026-06-03 18:00:00")
        await admin_shifts.create_shift("s2", "2026-06-03 21:00:00", "2026-06-04 03:00:00")
        nxt = await shifts_query.next_shift_start(when="2026-06-03 12:00:00")
        assert nxt == "2026-06-03T21:00:00Z"

    async def test_overnight_shift(self, db_ready) -> None:
        # 跨日班次（晚班 21:00 → 次日 03:00）：在 19:00 查应返回 21:00
        await admin_shifts.create_shift("s1", "2026-06-03 21:00:00", "2026-06-04 03:00:00")
        nxt = await shifts_query.next_shift_start(when="2026-06-03 19:00:00")
        assert nxt == "2026-06-03T21:00:00Z"


class TestToIsoUtc:
    """_to_iso_utc 规范化：DB 里的旧字符串格式 → ISO 8601 with Z。"""

    def test_space_separator_format(self) -> None:
        assert shifts_query._to_iso_utc("2026-06-04 09:00:00") == "2026-06-04T09:00:00Z"

    def test_already_iso_no_z(self) -> None:
        assert shifts_query._to_iso_utc("2026-06-04T09:00:00") == "2026-06-04T09:00:00Z"

    def test_already_iso_with_z(self) -> None:
        # 已经规范化的输入应原样返回（或等价：仍是 Z 结尾）
        assert shifts_query._to_iso_utc("2026-06-04T09:00:00Z") == "2026-06-04T09:00:00Z"

    def test_iso_with_offset(self) -> None:
        # +00:00 等价于 Z，应转成 Z 形式
        assert shifts_query._to_iso_utc("2026-06-04T09:00:00+00:00") == "2026-06-04T09:00:00Z"

    def test_invalid_falls_back(self) -> None:
        # 解析不了时回退原值（防御性，不让此函数把转人工流程打断）
        assert shifts_query._to_iso_utc("not a date") == "not a date"
