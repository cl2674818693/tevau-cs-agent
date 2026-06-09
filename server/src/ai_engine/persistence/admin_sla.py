"""SLA 策略 CRUD + 进行中违规计算（运行时算，不落 breach 表）。"""

from datetime import UTC, datetime
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_METRICS = {"take_time", "resolve_time"}


async def create_policy(
    metric: str, threshold_seconds: int, scope: str, scope_value: str | None
) -> int:
    if metric not in _VALID_METRICS:
        raise ValueError("invalid metric")
    return await db.insert_returning_id(
        "INSERT INTO sla_policies(metric, threshold_seconds, scope, scope_value, created_at) "
        "VALUES (:m, :th, :sc, :sv, :now)",
        {
            "m": metric,
            "th": int(threshold_seconds),
            "sc": scope,
            "sv": scope_value,
            "now": now_str(),
        },
    )


async def list_policies() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, metric, threshold_seconds, scope, scope_value, active, created_at "
        "FROM sla_policies ORDER BY id"
    )


async def set_policy_active(policy_id: int, active: int) -> int:
    """切换 active；返回受影响行数（0 表示 policy_id 不存在）。"""
    return await db.execute_rowcount(
        "UPDATE sla_policies SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(policy_id)},
    )


async def delete_policy(policy_id: int) -> int:
    """删除策略；返回受影响行数（0 表示 policy_id 不存在，端点用于 404 判定）。"""
    return await db.execute_rowcount(
        "DELETE FROM sla_policies WHERE id = :id", {"id": int(policy_id)}
    )


def _elapsed(since: str) -> float:
    return (datetime.now(UTC).replace(tzinfo=None) - datetime.fromisoformat(since)).total_seconds()


async def compute_breaches() -> list[dict[str, Any]]:
    """当前进行中且已超阈值的违规列表（告警用）。

    take_time: 仍未接管(mode=human_pending 且无 take 记录)且 now-created_at>阈值。
    resolve_time: 已接管(有 take)未 resolved 且 now-take>阈值。
    """
    policies = [p for p in await list_policies() if int(p["active"]) == 1]
    if not policies:
        return []
    take_thr = min(
        (int(p["threshold_seconds"]) for p in policies if p["metric"] == "take_time"),
        default=None,
    )
    resolve_thr = min(
        (int(p["threshold_seconds"]) for p in policies if p["metric"] == "resolve_time"),
        default=None,
    )

    breaches: list[dict[str, Any]] = []
    convs = await db.fetch_all(
        "SELECT id, user_type, subject_id, mode, created_at FROM conversations WHERE archived = 0"
    )
    for c in convs:
        cid = int(c["id"])
        take = await db.fetch_one(
            "SELECT at FROM staff_actions WHERE conversation_id = :cid AND action = 'take' "
            "ORDER BY id LIMIT 1",
            {"cid": cid},
        )
        ended = await db.fetch_one(
            "SELECT at FROM staff_actions WHERE conversation_id = :cid "
            "AND action IN ('resolved','release','transfer_out') ORDER BY id DESC LIMIT 1",
            {"cid": cid},
        )
        if take_thr is not None and take is None and str(c["mode"]) == "human_pending":
            el = _elapsed(str(c["created_at"]))
            if el > take_thr:
                breaches.append({"conversation_id": cid, "metric": "take_time",
                                 "elapsed_seconds": int(el), "threshold_seconds": take_thr})
        if resolve_thr is not None and take is not None and ended is None:
            el = _elapsed(str(take["at"]))
            if el > resolve_thr:
                breaches.append({"conversation_id": cid, "metric": "resolve_time",
                                 "elapsed_seconds": int(el), "threshold_seconds": resolve_thr})
    return breaches
