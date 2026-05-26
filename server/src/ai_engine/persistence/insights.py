"""知识缺口聚合：把"AI 差了什么"的可靠信号汇总成报表口径。

四项信号（均可结构化查询，避免脆弱的 payload_json 文本匹配）：
- out_of_scope：话题分类判定 no 的用户消息数（被判超范围/答不了）
- failed_turns：回合 status=failed 数（LLM/工具失败或僵尸超时）
- thumbs_down：消息级 👎 数
- human_handoff：进入人工通道的会话数（mode IN human_pending/human_takeover）
另有 tool_health（按工具的空结果率/拒绝率）与 gap_conversations（按信号下钻到会话）。
按 created_at 字符串窗口过滤（沿用项目时间列约定，定宽格式字典序==时间序）。
"""

from typing import Any

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
# 转人工：会话粒度计数（mode 进入人工通道）。用 conversations.created_at 做窗口。
_Q_HUMAN_HANDOFF = (
    "SELECT COUNT(*) AS n FROM conversations "
    "WHERE mode IN ('human_pending','human_takeover') "
    "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)

# 工具健康度：按 tool_name 聚合调用/空结果/拒绝。is_empty 历史行可能为 NULL，
# 用 CASE 把 NULL/0 都当作非空，避免 SUM(NULL) 干扰。全字面量 SQL。
_Q_TOOL_HEALTH = (
    "SELECT tool_name, "
    "COUNT(*) AS calls, "
    "SUM(CASE WHEN is_empty=1 THEN 1 ELSE 0 END) AS empty, "
    "SUM(CASE WHEN rejected=1 THEN 1 ELSE 0 END) AS rejected "
    "FROM tool_audits "
    "WHERE (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt) "
    "GROUP BY tool_name ORDER BY calls DESC"
)


async def _count(sql: str, date_from: str | None, date_to: str | None) -> int:
    row = await db.fetch_one(sql, {"df": date_from, "dt": date_to})
    return int(row["n"]) if row else 0


async def knowledge_gaps(date_from: str | None, date_to: str | None) -> dict[str, int]:
    return {
        "out_of_scope": await _count(_Q_OUT_OF_SCOPE, date_from, date_to),
        "failed_turns": await _count(_Q_FAILED, date_from, date_to),
        "thumbs_down": await _count(_Q_THUMBS_DOWN, date_from, date_to),
        "human_handoff": await _count(_Q_HUMAN_HANDOFF, date_from, date_to),
    }


async def tool_health(
    date_from: str | None, date_to: str | None
) -> list[dict[str, Any]]:
    """按 tool_name 聚合：calls / empty / rejected，Python 侧算 empty_rate（防除零）。"""
    rows = await db.fetch_all(_Q_TOOL_HEALTH, {"df": date_from, "dt": date_to})
    out: list[dict[str, Any]] = []
    for r in rows:
        calls = int(r["calls"]) if r["calls"] is not None else 0
        empty = int(r["empty"]) if r["empty"] is not None else 0
        rejected = int(r["rejected"]) if r["rejected"] is not None else 0
        out.append(
            {
                "tool_name": r["tool_name"],
                "calls": calls,
                "empty": empty,
                "rejected": rejected,
                "empty_rate": (empty / calls) if calls else 0.0,
            }
        )
    return out


# 下钻：信号 -> 取对应会话 id 的固定 SQL 片段。kind 仅作白名单键，绝不拼进 SQL。
# 各查询返回 conversation_id + last_at（最近时间，供前端排序展示）。时间窗用各自表的 created_at。
_GAP_QUERIES: dict[str, str] = {
    "out_of_scope": (
        "SELECT conversation_id, MAX(created_at) AS last_at FROM messages "
        "WHERE role='user' AND topic_verdict='no' "
        "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt) "
        "GROUP BY conversation_id ORDER BY last_at DESC LIMIT :lim"
    ),
    "failed": (
        "SELECT conversation_id, MAX(created_at) AS last_at FROM messages "
        "WHERE role='user' AND status='failed' "
        "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt) "
        "GROUP BY conversation_id ORDER BY last_at DESC LIMIT :lim"
    ),
    "thumbs_down": (
        "SELECT conversation_id, MAX(created_at) AS last_at FROM message_feedback "
        "WHERE rating='down' "
        "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt) "
        "GROUP BY conversation_id ORDER BY last_at DESC LIMIT :lim"
    ),
    "human_handoff": (
        "SELECT id AS conversation_id, created_at AS last_at FROM conversations "
        "WHERE mode IN ('human_pending','human_takeover') "
        "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt) "
        "ORDER BY last_at DESC LIMIT :lim"
    ),
}


async def gap_conversations(
    kind: str,
    date_from: str | None,
    date_to: str | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按知识缺口信号下钻到会话列表。

    kind 白名单：out_of_scope / failed / thumbs_down / human_handoff。
    非法 kind 直接 raise ValueError（绝不把 kind 拼进 SQL）。
    返回 [{conversation_id, last_at}]，按最近时间倒序。
    """
    sql = _GAP_QUERIES.get(kind)
    if sql is None:
        raise ValueError(f"invalid gap kind: {kind!r}")
    rows = await db.fetch_all(
        sql, {"df": date_from, "dt": date_to, "lim": limit}
    )
    return [
        {"conversation_id": int(r["conversation_id"]), "last_at": r["last_at"]}
        for r in rows
    ]
