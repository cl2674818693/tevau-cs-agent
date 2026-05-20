from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# TODO: 接到真实 schema 后校对表名/字段；并明确 request_json/response_json 内需脱敏的字段
SQL = """
SELECT uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at
FROM api_call_log
WHERE uid=%s AND bu_id=%s
"""


async def run(bu_id: str, uid: str) -> dict[str, Any]:
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (uid, bu_id))
    if not row:
        return {"call": None, "note": f"uid {uid} not found for BU {bu_id}"}
    return {"call": row}


register(
    Tool(
        name="query_api_call",
        description="按 uid（请求唯一 ID）查询一次 API 调用的日志（仅限当前 BU）。",
        input_schema={
            "type": "object",
            "properties": {
                "bu_id": {"type": "string"},
                "uid": {"type": "string"},
            },
            "required": ["uid"],
        },
        handler=run,
        requires_subject_id=True,
    )
)
