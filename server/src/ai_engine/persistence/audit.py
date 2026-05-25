import json

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def log_tool_call(
    conversation_id: int,
    tool_name: str,
    params: dict[str, object],
    result_size: int,
    duration_ms: int,
    rejected: bool,
    reject_reason: str | None,
) -> int:
    return await db.insert_returning_id(
        """INSERT INTO tool_audits
        (conversation_id, tool_name, params_json, result_size, duration_ms,
         rejected, reject_reason, created_at)
        VALUES (:cid, :name, :params, :size, :ms, :rej, :reason, :now) RETURNING id""",
        {
            "cid": conversation_id,
            "name": tool_name,
            "params": json.dumps(params, ensure_ascii=False),
            "size": result_size,
            "ms": duration_ms,
            "rej": 1 if rejected else 0,
            "reason": reject_reason,
            "now": now_str(),
        },
    )


async def list_audits(conversation_id: int) -> list[dict[str, object]]:
    return await db.fetch_all(
        "SELECT id, tool_name, params_json, result_size, duration_ms, "
        "rejected, reject_reason, created_at "
        "FROM tool_audits WHERE conversation_id=:cid ORDER BY id",
        {"cid": conversation_id},
    )
