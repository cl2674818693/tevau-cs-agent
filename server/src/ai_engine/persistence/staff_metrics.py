"""客服动作埋点 + KPI 聚合（spec §13.4）。

staff_actions 记录 take/release/transfer_out/transfer_in/resolved，KPI 从中算
接管数、平均接管时长、释放回 AI 比例、解决率。
"""

from datetime import datetime
from typing import Any

from ai_engine.persistence.db import get_conn

_END_ACTIONS = {"release", "resolved", "transfer_out"}


async def log_staff_action(conv_id: int, staff_id: str, action: str) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO staff_actions(conversation_id, staff_id, action) VALUES (?,?,?)",
            (conv_id, staff_id, action),
        )
        await conn.commit()


async def _load_actions(date_from: str | None, date_to: str | None) -> list[dict[str, Any]]:
    sql = "SELECT conversation_id, staff_id, action, at FROM staff_actions"
    clauses, args = [], []
    if date_from:
        clauses.append("at >= ?")
        args.append(date_from)
    if date_to:
        clauses.append("at <= ?")
        args.append(date_to)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    async with get_conn() as conn:
        rows = await (await conn.execute(sql, tuple(args))).fetchall()
    return [dict(r) for r in rows]


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
