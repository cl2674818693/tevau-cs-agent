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


async def recent_audits(
    limit: int,
    rejected_only: bool = False,
    tool_name: str | None = None,
    empty_only: bool = False,
    conversation_id: int | None = None,
    before_id: int | None = None,
) -> list[dict[str, object]]:
    """跨会话近期工具调用审计流（最新在前）。

    支持可选筛选：
    - rejected_only: 只看被拒调用
    - tool_name: 按工具名过滤
    - empty_only: 只看空结果调用
    - conversation_id: 按会话过滤
    - before_id: 游标分页（id < before_id）

    WHERE 片段全为固定字符串，值全走绑定参数，不拼用户输入。
    """
    cols = (
        "id, conversation_id, tool_name, params_json, result_size, duration_ms, "
        "rejected, reject_reason, created_at, result_count, is_empty, subject_id, user_type"
    )
    where: list[str] = []
    binds: dict[str, object] = {"lim": limit}
    if rejected_only:
        where.append("rejected=1")
    if empty_only:
        where.append("is_empty=1")
    if tool_name is not None:
        where.append("tool_name=:tn")
        binds["tn"] = tool_name
    if conversation_id is not None:
        where.append("conversation_id=:cid")
        binds["cid"] = conversation_id
    if before_id is not None:
        where.append("id < :bid")
        binds["bid"] = before_id
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT {cols} FROM tool_audits{clause} ORDER BY id DESC LIMIT :lim"
    return await db.fetch_all(sql, binds)
