from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.db import get_conn


async def run(bu_id: str, card_id: str) -> dict[str, Any]:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT card_id, user_id, status, lock_reason FROM mock_cards "
                "WHERE card_id=? AND bu_id=?",
                (card_id, bu_id),
            )
        ).fetchone()
    if not row:
        return {"card": None, "note": f"card {card_id} not in BU {bu_id}"}
    return {"card": dict(row)}


register(
    Tool(
        name="query_card",
        description="查询卡片状态与锁定原因（仅限当前 BU 下）。",
        input_schema={
            "type": "object",
            "properties": {
                "bu_id": {"type": "string"},
                "card_id": {"type": "string"},
            },
            "required": ["card_id"],
        },
        handler=run,
        requires_subject_id=True,
    )
)
