"""排班查询 helper：判断某时刻 staff 是否在班 / 是否有任何客服在班 / 下一次有客服上班时间。

业务场景：用户班外转人工时，仍创建 human_pending（客服上班看得到），但 AI 要明告
"现在不在服务时间，下次上班是 X 时；已留工单，到时客服会主动联系您"。这一组函数支撑
该判断与措辞。

时间约定：DB 列存的是 UTC，但格式可能是 "YYYY-MM-DD HH:MM:SS"（now_str 写入的）或
"YYYY-MM-DDTHH:MM:SS"（admin POST 提交时透传）。next_shift_start 对外统一输出
ISO 8601 with Z 后缀（如 "2026-06-04T09:00:00Z"），让 AI 看到 Z 立刻知道是 UTC，
避免跨时区用户（葡语/印尼语/日语等）把裸字符串当本地时间误等。
"""

from datetime import datetime

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


def _to_iso_utc(raw: str) -> str:
    """把 DB 字符串规范化成 ISO 8601 with Z。兼容：
      - "2026-06-04 09:00:00"（now_str 格式）
      - "2026-06-04T09:00:00"（已 ISO 但缺 Z）
      - "2026-06-04T09:00:00Z" / "+00:00"（已规范化）
    无法解析时回退原值（防御性，不让此函数报错把转人工流程也打断）。"""
    try:
        # Python 3.11+ fromisoformat 支持 'Z' 与空格分隔（容错较宽）
        s = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(s.replace(" ", "T") if "T" not in s else s)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return raw


async def is_on_shift(staff_id: str, when: str | None = None) -> bool:
    """when 默认 now；返回 staff 是否处于某个 shift 时段内。"""
    when_ts = when or now_str()
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM staff_shifts "
        "WHERE staff_id = :sid AND start_at <= :when AND end_at >= :when LIMIT 1",
        {"sid": staff_id, "when": when_ts},
    )
    return row is not None


async def any_on_shift(when: str | None = None) -> bool:
    """when 默认 now；只要有任何一位 staff 处于排班时段内即返回 True。
    用于转人工入口判断"现在班内还是班外"。"""
    when_ts = when or now_str()
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM staff_shifts "
        "WHERE start_at <= :when AND end_at >= :when LIMIT 1",
        {"when": when_ts},
    )
    return row is not None


async def next_shift_start(when: str | None = None) -> str | None:
    """when 默认 now；返回**不早于 when**的最近一次客服 shift 开始时间。
    在班期间调用（start_at <= when <= end_at）会返回**下一段**新班次的起点，而非本班次。
    没有未来排班则返回 None（措辞回退为"已留工单，客服会尽快回复"）。"""
    when_ts = when or now_str()
    row = await db.fetch_one(
        "SELECT MIN(start_at) AS next_start FROM staff_shifts WHERE start_at > :when",
        {"when": when_ts},
    )
    if row is None or row.get("next_start") is None:
        return None
    return _to_iso_utc(str(row["next_start"]))
