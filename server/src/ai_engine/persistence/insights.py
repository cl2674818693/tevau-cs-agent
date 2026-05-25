"""知识缺口聚合：把"AI 差了什么"的可靠信号汇总成报表口径。

三项信号（均可结构化查询，避免脆弱的 payload_json 文本匹配）：
- out_of_scope：话题分类判定 no 的用户消息数（被判超范围/答不了）
- failed_turns：回合 status=failed 数（LLM/工具失败或僵尸超时）
- thumbs_down：消息级 👎 数
按 created_at 字符串窗口过滤（沿用项目时间列约定，定宽格式字典序==时间序）。
"""

from typing import Any

from ai_engine.persistence import db


def _range(date_from: str | None, date_to: str | None) -> tuple[str, dict[str, Any]]:
    clause, params = "", {}
    if date_from:
        clause += " AND created_at >= :df"
        params["df"] = date_from
    if date_to:
        clause += " AND created_at <= :dt"
        params["dt"] = date_to
    return clause, params


async def _count(sql: str, params: dict[str, Any]) -> int:
    row = await db.fetch_one(sql, params)
    return int(row["n"]) if row else 0


async def knowledge_gaps(date_from: str | None, date_to: str | None) -> dict[str, int]:
    rng, p = _range(date_from, date_to)
    return {
        "out_of_scope": await _count(
            f"SELECT COUNT(*) AS n FROM messages WHERE role='user' AND topic_verdict='no'{rng}", p
        ),
        "failed_turns": await _count(
            f"SELECT COUNT(*) AS n FROM messages WHERE role='user' AND status='failed'{rng}", p
        ),
        "thumbs_down": await _count(
            f"SELECT COUNT(*) AS n FROM message_feedback WHERE rating='down'{rng}", p
        ),
    }
