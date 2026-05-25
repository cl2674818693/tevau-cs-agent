import json
from datetime import UTC, datetime, timedelta

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_ticket(external_id: str, conversation_id: int, payload: dict[str, object]) -> None:
    await db.execute(
        "INSERT INTO tickets(external_id, conversation_id, payload_json, current_severity, "
        "created_at) VALUES (:eid, :cid, :payload, :sev, :now)",
        {
            "eid": external_id,
            "cid": conversation_id,
            "payload": json.dumps(payload, ensure_ascii=False),
            "sev": payload.get("severity"),
            "now": now_str(),
        },
    )


async def append_ticket_event(
    external_id: str,
    event: str,
    actor: str | None,
    comment: str | None,
    raw: dict[str, object] | None = None,
) -> None:
    await db.execute(
        "INSERT INTO ticket_events(external_id, event, actor, comment, raw_json, created_at) "
        "VALUES (:eid, :event, :actor, :comment, :raw, :now)",
        {
            "eid": external_id,
            "event": event,
            "actor": actor,
            "comment": comment,
            "raw": json.dumps(raw or {}, ensure_ascii=False),
            "now": now_str(),
        },
    )


async def find_open_ticket_for_subject(
    subject_id: str, user_type: str, within_hours: int = 24
) -> str | None:
    """spec §11 工单风暴对策：返回该 subject 在窗口内未关闭(closed)的工单 external_id。"""
    subject_key = "user_id" if user_type == "c" else "bu_id"
    # 时间窗口在 Python 算 cutoff（方言无关，替代 SQLite 专有 datetime('now','-N hours')）
    cutoff = (datetime.now(UTC) - timedelta(hours=int(within_hours))).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.fetch_all(
        """SELECT t.external_id, t.payload_json FROM tickets t
           WHERE t.created_at >= :cutoff
             AND NOT EXISTS (
                 SELECT 1 FROM ticket_events e
                 WHERE e.external_id = t.external_id AND e.event = 'closed'
             )
           ORDER BY t.created_at DESC""",
        {"cutoff": cutoff},
    )
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if payload.get(subject_key) == subject_id and payload.get("user_type") == user_type:
            return str(row["external_id"])
    return None


async def update_ticket_severity(external_id: str, severity: str) -> None:
    """spec 7.2: 受理人在事项中心覆盖 severity -> 更新本地镜像。"""
    await db.execute(
        "UPDATE tickets SET current_severity=:sev WHERE external_id=:eid",
        {"sev": severity, "eid": external_id},
    )


async def get_ticket(external_id: str) -> dict[str, object] | None:
    row = await db.fetch_one(
        """SELECT external_id, conversation_id, payload_json, current_severity, created_at
           FROM tickets WHERE external_id=:eid""",
        {"eid": external_id},
    )
    if not row:
        return None
    evs = await db.fetch_all(
        "SELECT event, actor, comment, created_at FROM ticket_events "
        "WHERE external_id=:eid ORDER BY id",
        {"eid": external_id},
    )
    row["events"] = evs
    return row
