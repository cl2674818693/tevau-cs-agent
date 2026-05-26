"""灰度变更审计持久化（Task 6.1）。"""

import json

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def log_prompt_change(
    actor: str,
    old_rollout: dict[str, int],
    new_rollout: dict[str, int],
) -> int:
    """记录一条灰度变更审计行，返回新行 id。"""
    return await db.insert_returning_id(
        """INSERT INTO prompt_changes (actor, old_json, new_json, created_at)
        VALUES (:actor, :old, :new, :now) RETURNING id""",
        {
            "actor": actor,
            "old": json.dumps(old_rollout, ensure_ascii=False),
            "new": json.dumps(new_rollout, ensure_ascii=False),
            "now": now_str(),
        },
    )


async def list_prompt_changes(limit: int = 50) -> list[dict[str, object]]:
    """返回最近 limit 条变更记录（最新在前）。"""
    return await db.fetch_all(
        "SELECT id, actor, old_json, new_json, created_at "
        "FROM prompt_changes ORDER BY id DESC LIMIT :lim",
        {"lim": limit},
    )
