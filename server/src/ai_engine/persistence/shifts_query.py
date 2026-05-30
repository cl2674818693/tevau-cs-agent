"""排班查询 helper：判断某时刻 staff 是否在班。"""

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def is_on_shift(staff_id: str, when: str | None = None) -> bool:
    """when 默认 now；返回 staff 是否处于某个 shift 时段内。"""
    when_ts = when or now_str()
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM staff_shifts "
        "WHERE staff_id = :sid AND start_at <= :when AND end_at >= :when LIMIT 1",
        {"sid": staff_id, "when": when_ts},
    )
    return row is not None
