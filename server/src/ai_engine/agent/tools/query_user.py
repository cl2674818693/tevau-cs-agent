from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_email, mask_phone
from ai_engine.persistence.business_db import get_db

# TODO: 接到真实 unlimitpay_test schema 后校对表名/字段（spec §12.2 第 9 条）
SQL = """
SELECT user_id, bu_id, email, phone, status
FROM user
WHERE user_id=%s AND bu_id=%s
"""


async def run(bu_id: str, user_id: str, unmask: bool = False) -> dict[str, Any]:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (user_id, bu_id))
    if not row:
        return {"user": None, "note": f"user {user_id} not in BU {bu_id}"}
    # 脱敏在 handler 内做（spec §5.4）；unmask 仅 engineer 代查时 True（§13.3）
    email = row.get("email")
    phone = row.get("phone")
    return {
        "user": {
            "user_id": row["user_id"],
            "bu_id": row["bu_id"],
            "email": email if unmask else mask_email(email),
            "phone": phone if unmask else mask_phone(phone),
            "status": row.get("status"),
        },
        "unmasked": unmask,
    }


register(
    Tool(
        name="query_user",
        description="查询某个 user 的基本信息（仅限当前 BU 下，敏感字段已脱敏）。",
        input_schema={
            "type": "object",
            "properties": {
                "bu_id": {"type": "string"},  # router 强制注入
                "user_id": {"type": "string"},
            },
            "required": ["user_id"],
        },
        handler=run,
        requires_subject_id=True,
        supports_unmask=True,
    )
)
