"""成本治理（spec §8）：单 BU/单 user 单日 token 硬阈值。

80% 提醒、100% 拒服。额度按自然日（UTC）累计。
"""

from datetime import UTC, datetime
from typing import Any

from ai_engine.config import settings
from ai_engine.persistence import db

_WARN_RATIO = 0.8


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


async def _get_used(subject_id: str, user_type: str, day: str) -> tuple[int, int]:
    # M4: 读 by-model 表 SUM 各 model 行得当日总额（旧表已删）
    row = await db.fetch_one(
        "SELECT COALESCE(SUM(input_tokens), 0) AS in_t, "
        "COALESCE(SUM(output_tokens), 0) AS out_t "
        "FROM daily_token_usage_by_model "
        "WHERE subject_id=:sid AND user_type=:ut AND date=:day",
        {"sid": subject_id, "ut": user_type, "day": day},
    )
    if not row:
        return 0, 0
    return int(row["in_t"]), int(row["out_t"])


async def _record(
    subject_id: str,
    user_type: str,
    day: str,
    in_tok: int,
    out_tok: int,
    model: str | None = None,
) -> None:
    # M4: 只写 by-model 拆分表（旧表已删）；model None 时用 "(unknown)" 占位。
    # 方言分发：累加 upsert（SQLite ON CONFLICT / MySQL ON DUPLICATE KEY UPDATE）。
    # MySQL 写法里裸 input_tokens 引用的是已存在行的原值（标准语义），等价 PG 的 table.input_tokens。
    m = model if model else "(unknown)"
    if db.dialect_name() == "mysql":
        sql = (
            "INSERT INTO daily_token_usage_by_model"
            "(subject_id, user_type, date, model, input_tokens, output_tokens) "
            "VALUES (:s, :u, :d, :m, :it, :ot) "
            "ON DUPLICATE KEY UPDATE "
            "input_tokens = input_tokens + :it, "
            "output_tokens = output_tokens + :ot"
        )
    else:
        sql = (
            "INSERT INTO daily_token_usage_by_model"
            "(subject_id, user_type, date, model, input_tokens, output_tokens) "
            "VALUES (:s, :u, :d, :m, :it, :ot) "
            "ON CONFLICT(subject_id, user_type, date, model) DO UPDATE SET "
            "input_tokens = daily_token_usage_by_model.input_tokens + :it, "
            "output_tokens = daily_token_usage_by_model.output_tokens + :ot"
        )
    await db.execute(
        sql,
        {"s": subject_id, "u": user_type, "d": day,
         "m": m, "it": int(in_tok), "ot": int(out_tok)},
    )


async def is_exhausted(user_type: str, subject_id: str) -> bool:
    """入口硬闸：当日额度已用尽则 True，调用方应直接拒绝、不进 agent loop（省一次昂贵 LLM 调用）。

    注意：进程内 daily_token_usage 已落 DB，跨副本一致；但 rate_limit 仍是进程内（见该模块说明）。
    """
    used_in, used_out = await _get_used(subject_id, user_type, _today())
    return (used_in + used_out) >= int(settings.daily_token_limit)


async def check_and_record(
    user_type: str,
    subject_id: str,
    input_tok: int,
    output_tok: int,
    model: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """返回 (allowed, info)。已达上限则拒服（不记账）；否则记账并返回是否需 80% 提醒。

    M2: 可选 model 参数，落到 daily_token_usage.model 列（成本大盘按模型聚合）。
    """
    day = _today()
    limit = settings.daily_token_limit
    used_in, used_out = await _get_used(subject_id, user_type, day)
    used_total = used_in + used_out
    if used_total >= limit:
        return False, {"used": used_total, "limit": limit}
    await _record(subject_id, user_type, day, input_tok, output_tok, model=model)
    new_total = used_total + input_tok + output_tok
    return True, {"used": new_total, "limit": limit, "warn": new_total / limit > _WARN_RATIO}
