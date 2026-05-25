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
            staff, {"takeovers": 0, "releases": 0, "resolved": 0, "_handle_seconds": []}
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
            start = open_takes.pop((staff, conv), None)
            if start:
                s["_handle_seconds"].append((_parse(at) - _parse(start)).total_seconds())
    return agg


def _finalize(agg: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for staff, s in agg.items():
        takeovers = s["takeovers"]
        handle = s["_handle_seconds"]
        out.append(
            {
                "staff_id": staff,
                "takeovers": takeovers,
                "releases": s["releases"],
                "resolved": s["resolved"],
                "release_ratio": round(s["releases"] / takeovers, 3) if takeovers else 0.0,
                "resolved_ratio": round(s["resolved"] / takeovers, 3) if takeovers else 0.0,
                "avg_handle_seconds": round(sum(handle) / len(handle), 1) if handle else 0.0,
            }
        )
    return sorted(out, key=lambda x: x["staff_id"])


async def compute_kpi(date_from: str | None, date_to: str | None) -> list[dict[str, Any]]:
    return _finalize(_aggregate(await _load_actions(date_from, date_to)))
