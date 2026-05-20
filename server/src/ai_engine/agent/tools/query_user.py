from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.db import get_conn


async def run(bu_id: str, user_id: str) -> dict[str, Any]:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT user_id, bu_id, email, status FROM mock_users WHERE user_id=? AND bu_id=?",
                (user_id, bu_id),
            )
        ).fetchone()
    if not row:
        return {"user": None, "note": f"user {user_id} not in BU {bu_id}"}
    return {"user": dict(row)}


register(
    Tool(
        name="query_user",
        description="查询某个 user 的基本信息（仅限当前 BU 下的 user）。",
        input_schema={
            "type": "object",
            "properties": {
                "bu_id": {"type": "string"},  # router 会强制注入
                "user_id": {"type": "string"},
            },
            "required": ["user_id"],
        },
        handler=run,
        requires_subject_id=True,
    )
)
