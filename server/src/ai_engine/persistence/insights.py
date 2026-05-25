"""知识缺口聚合：把"AI 差了什么"的可靠信号汇总成报表口径。

三项信号（均可结构化查询，避免脆弱的 payload_json 文本匹配）：
- out_of_scope：话题分类判定 no 的用户消息数（被判超范围/答不了）
- failed_turns：回合 status=failed 数（LLM/工具失败或僵尸超时）
- thumbs_down：消息级 👎 数
按 created_at 字符串窗口过滤（沿用项目时间列约定，定宽格式字典序==时间序）。
"""

from ai_engine.persistence import db

# 全字面量 SQL（无动态构造）。时间窗用 :df/:dt 恒定绑定，None 时谓词短路。
_Q_OUT_OF_SCOPE = (
    "SELECT COUNT(*) AS n FROM messages "
    "WHERE role='user' AND topic_verdict='no' "
    "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)
_Q_FAILED = (
    "SELECT COUNT(*) AS n FROM messages "
    "WHERE role='user' AND status='failed' "
    "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)
_Q_THUMBS_DOWN = (
    "SELECT COUNT(*) AS n FROM message_feedback "
    "WHERE rating='down' "
    "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)


async def _count(sql: str, date_from: str | None, date_to: str | None) -> int:
    row = await db.fetch_one(sql, {"df": date_from, "dt": date_to})
    return int(row["n"]) if row else 0


async def knowledge_gaps(date_from: str | None, date_to: str | None) -> dict[str, int]:
    return {
        "out_of_scope": await _count(_Q_OUT_OF_SCOPE, date_from, date_to),
        "failed_turns": await _count(_Q_FAILED, date_from, date_to),
        "thumbs_down": await _count(_Q_THUMBS_DOWN, date_from, date_to),
    }
