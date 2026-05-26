"""客服动作埋点 + KPI 聚合（spec §13.4）。

staff_actions 记录 take/release/transfer_out/transfer_in/resolved，KPI 从中算
接管数、平均接管时长、释放回 AI 比例、解决率。
"""

from datetime import UTC, datetime
from typing import Any

from ai_engine.observability import metrics
from ai_engine.persistence import db
from ai_engine.persistence.conversations import count_pending
from ai_engine.persistence.schema import now_str


async def refresh_human_pending() -> None:
    """按 DB 真实计数刷新 human_pending gauge（在改 mode 的端点调用）。"""
    metrics.human_pending.set(await count_pending())


_END_ACTIONS = {"release", "resolved", "transfer_out"}


async def log_staff_action(conv_id: int, staff_id: str, action: str) -> None:
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:cid, :sid, :action, :now)",
        {"cid": conv_id, "sid": staff_id, "action": action, "now": now_str()},
    )
    if action not in _END_ACTIONS:
        return
    row = await db.fetch_one(
        "SELECT at FROM staff_actions WHERE conversation_id=:cid AND staff_id=:sid "
        "AND action='take' ORDER BY id DESC LIMIT 1",
        {"cid": conv_id, "sid": staff_id},
    )
    if row:
        elapsed = (datetime.now(UTC).replace(tzinfo=None) - _parse(row["at"])).total_seconds()
        if elapsed >= 0:
            metrics.staff_takeover_seconds.labels(staff_id=staff_id).observe(elapsed)


async def _load_actions(date_from: str | None, date_to: str | None) -> list[dict[str, Any]]:
    sql = "SELECT conversation_id, staff_id, action, at FROM staff_actions"
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if date_from:
        clauses.append("at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        clauses.append("at <= :date_to")
        params["date_to"] = date_to
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return await db.fetch_all(sql, params)


def _parse(at: str) -> datetime:
    return datetime.fromisoformat(at)


def _aggregate(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    # 每客服累计；接管时长用 take→后续 end 动作配对（同会话同客服）
    agg: dict[str, dict[str, Any]] = {}
    open_takes: dict[tuple[str, int], str] = {}  # (staff, conv) → take 时间

    def slot(staff: str) -> dict[str, Any]:
        return agg.setdefault(
            staff,
            {
                "takeovers": 0,
                "releases": 0,
                "resolved": 0,
                "transfers": 0,
                "_handle_seconds": [],
            },
        )

    for a in actions:
        staff, conv, action, at = a["staff_id"], a["conversation_id"], a["action"], a["at"]
        s = slot(staff)
        if action == "take":
            s["takeovers"] += 1
            open_takes[(staff, conv)] = at
        elif action in _END_ACTIONS:
            if action == "release":
                s["releases"] += 1
            elif action == "resolved":
                s["resolved"] += 1
            elif action == "transfer_out":
                s["transfers"] += 1
            start = open_takes.pop((staff, conv), None)
            if start:
                s["_handle_seconds"].append((_parse(at) - _parse(start)).total_seconds())
    return agg


def _finalize(agg: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for staff, s in agg.items():
        takeovers = s["takeovers"]
        releases = s["releases"]
        resolved = s["resolved"]
        transfers = s["transfers"]
        handle = s["_handle_seconds"]
        # 口径修正（Task 5.1）：release_ratio / resolved_ratio 的分母原先用 takeovers，
        # 但 transfer_out 收尾的接管既不计 releases 也不计 resolved，会稀释分母、低估比率。
        # 新口径：分母只取"自行收尾"的接管（resolved + release，即排除 transfer_out），
        # 使分子分母口径一致；transfer_out 单列 transfer_ratio（占全部接管比例）。
        resolution_base = releases + resolved
        out.append(
            {
                "staff_id": staff,
                "takeovers": takeovers,
                "releases": releases,
                "resolved": resolved,
                "transfers": transfers,
                "release_ratio": (
                    round(releases / resolution_base, 3) if resolution_base else 0.0
                ),
                "resolved_ratio": (
                    round(resolved / resolution_base, 3) if resolution_base else 0.0
                ),
                "transfer_ratio": round(transfers / takeovers, 3) if takeovers else 0.0,
                "avg_handle_seconds": round(sum(handle) / len(handle), 1) if handle else 0.0,
            }
        )
    return sorted(out, key=lambda x: x["staff_id"])


async def compute_kpi(date_from: str | None, date_to: str | None) -> list[dict[str, Any]]:
    return _finalize(_aggregate(await _load_actions(date_from, date_to)))


# 全局 AI 质量指标（Task 5.1）。各表用自身 created_at 做窗口（定宽字符串字典序==时间序，
# 与项目其他查询一致）。conversations 无独立时间列时复用 created_at。全字面量 SQL。
_Q_TOTAL_CONV = (
    "SELECT COUNT(*) AS n FROM conversations "
    "WHERE (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)
_Q_HANDOFF = (
    "SELECT COUNT(*) AS n FROM conversations "
    "WHERE mode IN ('human_pending','human_takeover') "
    "AND (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)
_Q_FEEDBACK = (
    "SELECT "
    "SUM(CASE WHEN rating='up' THEN 1 ELSE 0 END) AS up, "
    "SUM(CASE WHEN rating='down' THEN 1 ELSE 0 END) AS down "
    "FROM message_feedback "
    "WHERE (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)
_Q_TOOL = (
    "SELECT COUNT(*) AS calls, "
    "SUM(CASE WHEN is_empty=1 THEN 1 ELSE 0 END) AS empty "
    "FROM tool_audits "
    "WHERE (:df IS NULL OR created_at >= :df) AND (:dt IS NULL OR created_at <= :dt)"
)


async def ai_quality(date_from: str | None, date_to: str | None) -> dict[str, Any]:
    """全局 AI 质量指标：转人工率 / 差评率 / 工具空结果率 + 超范围/失败回合数。

    所有比率防除零（分母 0 时返回 0.0）。out_of_scope / failed_turns 复用
    insights.knowledge_gaps 的口径，避免重复造轮子。
    """
    from ai_engine.persistence import insights

    params = {"df": date_from, "dt": date_to}
    total_row = await db.fetch_one(_Q_TOTAL_CONV, params)
    handoff_row = await db.fetch_one(_Q_HANDOFF, params)
    fb_row = await db.fetch_one(_Q_FEEDBACK, params)
    tool_row = await db.fetch_one(_Q_TOOL, params)
    gaps = await insights.knowledge_gaps(date_from, date_to)

    total = int(total_row["n"]) if total_row else 0
    handoff = int(handoff_row["n"]) if handoff_row else 0
    upvote = int(fb_row["up"]) if fb_row and fb_row["up"] is not None else 0
    downvote = int(fb_row["down"]) if fb_row and fb_row["down"] is not None else 0
    tool_calls = int(tool_row["calls"]) if tool_row and tool_row["calls"] is not None else 0
    tool_empty = int(tool_row["empty"]) if tool_row and tool_row["empty"] is not None else 0
    fb_total = upvote + downvote

    return {
        "total_conversations": total,
        "handoff": handoff,
        "handoff_rate": (handoff / total) if total else 0.0,
        "upvote": upvote,
        "downvote": downvote,
        "downvote_rate": (downvote / fb_total) if fb_total else 0.0,
        "tool_calls": tool_calls,
        "tool_empty": tool_empty,
        "tool_empty_rate": (tool_empty / tool_calls) if tool_calls else 0.0,
        "out_of_scope": gaps["out_of_scope"],
        "failed_turns": gaps["failed_turns"],
    }
