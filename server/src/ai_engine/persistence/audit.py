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
    result_count: int | None = None,
    is_empty: bool | None = None,
    subject_id: str | None = None,
    user_type: str | None = None,
) -> int:
    return await db.insert_returning_id(
        """INSERT INTO tool_audits
        (conversation_id, tool_name, params_json, result_size, duration_ms,
         rejected, reject_reason, result_count, is_empty, subject_id, user_type, created_at)
        VALUES (:cid, :name, :params, :size, :ms, :rej, :reason,
                :result_count, :is_empty, :subject_id, :user_type, :now) RETURNING id""",
        {
            "cid": conversation_id,
            "name": tool_name,
            "params": json.dumps(params, ensure_ascii=False),
            "size": result_size,
            "ms": duration_ms,
            "rej": 1 if rejected else 0,
            "reason": reject_reason,
            "result_count": result_count,
            "is_empty": 1 if is_empty else (0 if is_empty is not None else None),
            "subject_id": subject_id,
            "user_type": user_type,
            "now": now_str(),
        },
    )


async def list_audits(conversation_id: int) -> list[dict[str, object]]:
    return await db.fetch_all(
        "SELECT id, tool_name, params_json, result_size, duration_ms, "
        "rejected, reject_reason, result_count, is_empty, subject_id, user_type, created_at "
        "FROM tool_audits WHERE conversation_id=:cid ORDER BY id",
        {"cid": conversation_id},
    )


# 全局近期工具调用审计：全部 / 仅被拒。limit 由调用方钳制，谓词用恒定绑定避免动态拼 SQL。
_RECENT_ALL = (
    "SELECT id, conversation_id, tool_name, params_json, result_size, duration_ms, "
    "rejected, reject_reason, result_count, is_empty, subject_id, user_type, created_at "
    "FROM tool_audits ORDER BY id DESC LIMIT :lim"
)
_RECENT_REJECTED = (
    "SELECT id, conversation_id, tool_name, params_json, result_size, duration_ms, "
    "rejected, reject_reason, result_count, is_empty, subject_id, user_type, created_at "
    "FROM tool_audits WHERE rejected=1 "
    "ORDER BY id DESC LIMIT :lim"
)


async def recent_audits(limit: int, rejected_only: bool) -> list[dict[str, object]]:
    """跨会话近期工具调用审计流（最新在前）。rejected_only=True 只看被拒调用。"""
    sql = _RECENT_REJECTED if rejected_only else _RECENT_ALL
    return await db.fetch_all(sql, {"lim": limit})
