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
    row = await db.fetch_one(
        "SELECT input_tokens, output_tokens FROM daily_token_usage "
        "WHERE subject_id=:sid AND user_type=:ut AND date=:day",
        {"sid": subject_id, "ut": user_type, "day": day},
    )
    if not row:
        return 0, 0
    return int(row["input_tokens"]), int(row["output_tokens"])


async def _record(
    subject_id: str,
    user_type: str,
    day: str,
    in_tok: int,
    out_tok: int,
    model: str | None = None,
) -> None:
    # ON CONFLICT...DO UPDATE...excluded. 两库（SQLite/Postgres）通用
    # M2: model 列写入；COALESCE+CAST 保留旧 model，仅当本次写入提供 model 时覆盖。
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, input_tokens, "
        "output_tokens, model) VALUES (:sid, :ut, :day, :in_tok, :out_tok, :model) "
        # 用表名限定累加列：PG 上裸列名在 DO UPDATE 里有歧义；SQLite 也接受表名限定
        "ON CONFLICT(subject_id, user_type, date) DO UPDATE SET "
        "input_tokens=daily_token_usage.input_tokens+excluded.input_tokens, "
        "output_tokens=daily_token_usage.output_tokens+excluded.output_tokens, "
        "model=COALESCE(CAST(:model AS TEXT), daily_token_usage.model)",
        {
            "sid": subject_id,
            "ut": user_type,
            "day": day,
            "in_tok": in_tok,
            "out_tok": out_tok,
            "model": model,
        },
    )
    # M3c: 双写 by-model 拆分表（model None 时跳过；旧表行为不变）。
    if model:
        await db.execute(
            "INSERT INTO daily_token_usage_by_model"
            "(subject_id, user_type, date, model, input_tokens, output_tokens) "
            "VALUES (:s, :u, :d, :m, :it, :ot) "
            "ON CONFLICT(subject_id, user_type, date, model) DO UPDATE SET "
            "input_tokens = daily_token_usage_by_model.input_tokens + :it, "
            "output_tokens = daily_token_usage_by_model.output_tokens + :ot",
            {"s": subject_id, "u": user_type, "d": day,
             "m": model, "it": int(in_tok), "ot": int(out_tok)},
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
