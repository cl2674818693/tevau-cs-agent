import re
from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_card_no
from ai_engine.persistence.business_db import get_db

# TODO: 接到真实 schema 后校对表名/字段
SQL = """
SELECT card_id, user_id, bu_id, card_no, status, lock_reason
FROM card
WHERE card_id=%s AND bu_id=%s
"""


def _translate_lock_reason(raw: str | None) -> str | None:
    """内部风控规则名 R-xxx → 业务原因（spec §5.4：不让 LLM 看到规则名）。"""
    if not raw:
        return raw
    return re.sub(r"R-\d{2,4}", "风控规则命中", raw)


async def run(bu_id: str, card_id: str, unmask: bool = False) -> dict[str, Any]:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (card_id, bu_id))
    if not row:
        return {"card": None, "note": f"card {card_id} not in BU {bu_id}"}
    # unmask 仅 engineer 代查时 True（§13.3）：还原全卡号与原始风控规则名
    card_no = row.get("card_no")
    lock_reason = row.get("lock_reason")
    return {
        "card": {
            "card_id": row["card_id"],
            "user_id": row["user_id"],
            "bu_id": row["bu_id"],
            "card_no": card_no if unmask else mask_card_no(card_no),
            "status": row.get("status"),
            "lock_reason": lock_reason if unmask else _translate_lock_reason(lock_reason),
        },
        "unmasked": unmask,
    }


register(
    Tool(
        name="query_card",
        description="查询卡片状态与锁定原因（仅当前 BU；卡号脱敏，规则名替换为业务原因）。",
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
        supports_unmask=True,
    )
)
