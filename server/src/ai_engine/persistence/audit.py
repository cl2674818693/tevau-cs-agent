import json

from ai_engine.persistence.db import get_conn


async def log_tool_call(
    conversation_id: int,
    tool_name: str,
    params: dict[str, object],
    result_size: int,
    duration_ms: int,
    rejected: bool,
    reject_reason: str | None,
) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            """INSERT INTO tool_audits
            (conversation_id, tool_name, params_json, result_size, duration_ms,
             rejected, reject_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                conversation_id,
                tool_name,
                json.dumps(params, ensure_ascii=False),
                result_size,
                duration_ms,
                1 if rejected else 0,
                reject_reason,
            ),
        )
        await conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid


async def list_audits(conversation_id: int) -> list[dict[str, object]]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, tool_name, params_json, result_size, duration_ms, "
                "rejected, reject_reason, created_at "
                "FROM tool_audits WHERE conversation_id=? ORDER BY id",
                (conversation_id,),
            )
        ).fetchall()
    return [dict(r) for r in rows]
