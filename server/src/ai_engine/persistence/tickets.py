import json

from ai_engine.persistence.db import get_conn


async def create_ticket(external_id: str, conversation_id: int, payload: dict[str, object]) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO tickets(external_id, conversation_id, payload_json, current_severity)
               VALUES (?, ?, ?, ?)""",
            (
                external_id,
                conversation_id,
                json.dumps(payload, ensure_ascii=False),
                payload.get("severity"),
            ),
        )
        await conn.commit()


async def append_ticket_event(
    external_id: str,
    event: str,
    actor: str | None,
    comment: str | None,
    raw: dict[str, object] | None = None,
) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO ticket_events(external_id, event, actor, comment, raw_json)
            VALUES (?, ?, ?, ?, ?)""",
            (external_id, event, actor, comment, json.dumps(raw or {}, ensure_ascii=False)),
        )
        await conn.commit()


async def find_open_ticket_for_subject(
    subject_id: str, user_type: str, within_hours: int = 24
) -> str | None:
    """spec §11 工单风暴对策：返回该 subject 在窗口内未关闭(closed)的工单 external_id。"""
    subject_key = "user_id" if user_type == "c" else "bu_id"
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                """SELECT t.external_id, t.payload_json FROM tickets t
                   WHERE t.created_at >= datetime('now', ?)
                     AND NOT EXISTS (
                         SELECT 1 FROM ticket_events e
                         WHERE e.external_id = t.external_id AND e.event = 'closed'
                     )
                   ORDER BY t.created_at DESC""",
                (f"-{int(within_hours)} hours",),
            )
        ).fetchall()
    for row in rows:
        payload = json.loads(str(row["payload_json"]))
        if payload.get(subject_key) == subject_id and payload.get("user_type") == user_type:
            return str(row["external_id"])
    return None


async def update_ticket_severity(external_id: str, severity: str) -> None:
    """spec 7.2: 受理人在事项中心覆盖 severity -> 更新本地镜像。"""
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE tickets SET current_severity=? WHERE external_id=?",
            (severity, external_id),
        )
        await conn.commit()


async def get_ticket(external_id: str) -> dict[str, object] | None:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                """SELECT external_id, conversation_id, payload_json, current_severity, created_at
                   FROM tickets WHERE external_id=?""",
                (external_id,),
            )
        ).fetchone()
        if not row:
            return None
        evs = await (
            await conn.execute(
                "SELECT event, actor, comment, created_at FROM ticket_events "
                "WHERE external_id=? ORDER BY id",
                (external_id,),
            )
        ).fetchall()
    out = dict(row)
    out["events"] = [dict(e) for e in evs]
    return out
