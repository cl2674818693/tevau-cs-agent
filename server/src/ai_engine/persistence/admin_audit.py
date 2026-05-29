"""后台统一操作审计：写入 + 查询。所有管理后台写操作调 log_admin_action 落痕。"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def log_admin_action(
    actor: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO admin_audit_log(actor, action, target_type, target_id, detail_json, created_at) "
        "VALUES (:actor, :action, :tt, :tid, :detail, :now) RETURNING id",
        {
            "actor": actor,
            "action": action,
            "tt": target_type,
            "tid": target_id,
            "detail": json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            "now": now_str(),
        },
    )


async def list_admin_actions(
    actor: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    # 可选筛选用 CAST(:p AS TEXT) 包裹，规避 Postgres 类型歧义
    return await db.fetch_all(
        "SELECT id, actor, action, target_type, target_id, detail_json, created_at "
        "FROM admin_audit_log "
        "WHERE (CAST(:actor AS TEXT) IS NULL OR actor = :actor) "
        "AND (CAST(:action AS TEXT) IS NULL OR action = :action) "
        "AND (CAST(:tt AS TEXT) IS NULL OR target_type = :tt) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {
            "actor": actor,
            "action": action,
            "tt": target_type,
            "df": date_from,
            "dt": date_to,
            "lim": limit,
            "off": offset,
        },
    )
