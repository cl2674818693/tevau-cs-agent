from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.db import get_conn


async def run(bu_id: str, uid: str) -> dict[str, Any]:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT uid, endpoint, status_code, error_code, request_json, "
                "response_json, created_at "
                "FROM mock_api_calls WHERE uid=? AND bu_id=?",
                (uid, bu_id),
            )
        ).fetchone()
    if not row:
        return {"call": None, "note": f"uid {uid} not found for BU {bu_id}"}
    return {"call": dict(row)}


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
