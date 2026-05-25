from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_trans_error（交易异常记录表），按 tenant_id 隔离。
# 区分异常归属：卡方异常 vs 平台异常 —— 定位"交易出问题到底是谁的锅"。
_BASE_SQL = """
SELECT trans_id, card_id, user_id, error_trans_code, trans_type, exception_type,
       reason, trans_body, create_time
FROM t_nexus_trans_error
WHERE tenant_id=%s AND del_flag=0
"""

_EXCEPTION_TYPE: dict[Any, str] = {1: "卡方异常", 2: "平台异常"}


def _clip(v: Any, n: int = 500) -> str | None:
    if v is None:
        return None
    s = v if isinstance(v, str) else str(v)
    return s[:n] + ("…" if len(s) > n else "")


async def run(tenant_id: str, card_id: str | None = None, unmask: bool = False) -> dict[str, Any]:
    """查某张卡的交易异常记录（异常 code、原因、卡方异常/平台异常）。交易报错/卡住排查用。"""
    if not tenant_id:
        return {"errors": [], "count": 0, "note": "缺少 tenant 身份"}
    sql = _BASE_SQL
    params: tuple[Any, ...] = (tenant_id,)
    if card_id:
        sql += " AND card_id=%s"
        params = (tenant_id, card_id)
    sql += " ORDER BY create_time DESC"
    db = get_db("nexus")
    rows = await db.fetch_all(sql, params, limit=20)
    errors = []
    for r in rows:
        item: dict[str, Any] = {
            "trans_id": r.get("trans_id"),
            "card_id": r.get("card_id"),
            "error_code": r.get("error_trans_code"),
            "trans_type": r.get("trans_type"),
            "exception_type": _EXCEPTION_TYPE.get(r.get("exception_type"), r.get("exception_type")),
            "reason": _clip(r.get("reason")),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        if unmask:  # engineer 代查：完整交易请求报文
            item["trans_body"] = _clip(r.get("trans_body"))
        errors.append(item)
    return {"errors": errors, "count": len(errors), "unmasked": unmask}


register(
    Tool(
        name="query_card_trans_error",
        description=(
            "查询某张卡的交易异常记录（t_nexus_trans_error）。"
            "能看到：异常 code、异常原因、归属（卡方异常/平台异常）。"
            "BU 问'交易报错''扣款异常''交易卡住了'时用，判断责任方在卡组织还是平台。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入
                "card_id": {"type": "string", "description": "按卡 id 过滤该卡的异常记录"},
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
