"""成本治理（spec §8）：单 BU/单 user 单日 token 硬阈值。

80% 提醒、100% 拒服。额度按自然日（UTC）累计。
"""

from datetime import UTC, datetime
from typing import Any

from ai_engine.config import settings
from ai_engine.persistence.db import get_conn

_WARN_RATIO = 0.8


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


async def _get_used(subject_id: str, user_type: str, day: str) -> tuple[int, int]:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT input_tokens, output_tokens FROM daily_token_usage "
                "WHERE subject_id=? AND user_type=? AND date=?",
                (subject_id, user_type, day),
            )
        ).fetchone()
    if not row:
        return 0, 0
    return int(row["input_tokens"]), int(row["output_tokens"])


async def _record(subject_id: str, user_type: str, day: str, in_tok: int, out_tok: int) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO daily_token_usage(subject_id, user_type, date, input_tokens, "
            "output_tokens) VALUES (?,?,?,?,?) "
            "ON CONFLICT(subject_id, user_type, date) DO UPDATE SET "
            "input_tokens=input_tokens+excluded.input_tokens, "
            "output_tokens=output_tokens+excluded.output_tokens",
            (subject_id, user_type, day, in_tok, out_tok),
        )
        await conn.commit()


async def is_exhausted(user_type: str, subject_id: str) -> bool:
    """入口硬闸：当日额度已用尽则 True，调用方应直接拒绝、不进 agent loop（省一次昂贵 LLM 调用）。

    注意：进程内 daily_token_usage 已落 DB，跨副本一致；但 rate_limit 仍是进程内（见该模块说明）。
    """
    used_in, used_out = await _get_used(subject_id, user_type, _today())
    return (used_in + used_out) >= int(settings.daily_token_limit)


async def check_and_record(
    user_type: str, subject_id: str, input_tok: int, output_tok: int
) -> tuple[bool, dict[str, Any]]:
    """返回 (allowed, info)。已达上限则拒服（不记账）；否则记账并返回是否需 80% 提醒。"""
    day = _today()
    limit = settings.daily_token_limit
    used_in, used_out = await _get_used(subject_id, user_type, day)
    used_total = used_in + used_out
    if used_total >= limit:
        return False, {"used": used_total, "limit": limit}
    await _record(subject_id, user_type, day, input_tok, output_tok)
    new_total = used_total + input_tok + output_tok
    return True, {"used": new_total, "limit": limit, "warn": new_total / limit > _WARN_RATIO}
