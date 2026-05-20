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
