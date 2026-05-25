from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_auth_callback（3DS / 卡消费授权回调记录），按 tenant_id 隔离。
# 这是判断"某笔卡消费是否走了 3DS、授权是否通过、商户是谁"的核心表。
_BASE_SQL = """
SELECT auth_id, card_id, card_pan, txn_currency, txn_amount, auth_status,
       card_acceptor_location_name, card_acceptor_location_country,
       remark, transaction_id, channel_type, created_time, request_param, response_param
FROM t_nexus_auth_callback
WHERE tenant_id=%s AND del_flag=0
"""

# auth_status：3DS / 授权状态。"已授权"=3DS 校验通过并放行；"失败/取消"需结合 remark 看原因。
_AUTH_STATUS: dict[Any, str] = {
    1: "未授权",
    2: "已授权",
    3: "授权取消",
    4: "授权超时",
    5: "失败",
}
_CHANNEL: dict[Any, str] = {1: "Reap", 2: "SX"}


async def run(tenant_id: str, card_id: str | None = None, unmask: bool = False) -> dict[str, Any]:
    """查某张卡的 3DS/消费授权回调（是否走 3DS、授权是否通过、商户、金额）。盗刷排查用。"""
    if not tenant_id:
        return {"authorizations": [], "count": 0, "note": "缺少 tenant 身份"}
    sql = _BASE_SQL
    params: tuple[Any, ...] = (tenant_id,)
    if card_id:
        sql += " AND card_id=%s"
        params = (tenant_id, card_id)
    sql += " ORDER BY created_time DESC"
    db = get_db("nexus")
    rows = await db.fetch_all(sql, params, limit=20)
    auths = []
    for r in rows:
        item: dict[str, Any] = {
            "auth_id": r.get("auth_id"),
            "card_id": r.get("card_id"),
            "card_pan": r.get("card_pan"),  # 入库即部分显示
            "auth_status_code": r.get("auth_status"),
            "auth_status": _AUTH_STATUS.get(r.get("auth_status"), f"未知({r.get('auth_status')})"),
            "amount": r.get("txn_amount"),
            "currency": r.get("txn_currency"),
            "merchant": r.get("card_acceptor_location_name"),
            "merchant_country": r.get("card_acceptor_location_country"),
            "channel": _CHANNEL.get(r.get("channel_type"), r.get("channel_type")),
            "transaction_id": r.get("transaction_id"),
            "remark": r.get("remark"),
            "created_time": str(r["created_time"]) if r.get("created_time") else None,
        }
        if unmask:  # engineer 代查：完整三方请求/响应报文
            item["request_param"] = r.get("request_param")
            item["response_param"] = r.get("response_param")
        auths.append(item)
    return {"authorizations": auths, "count": len(auths), "unmasked": unmask}


register(
    Tool(
        name="query_card_authorization",
        description=(
            "查询某张卡的 3DS / 消费授权回调记录（t_nexus_auth_callback）。"
            "能看到：是否走了 3DS（auth_status 是否'已授权'）、授权通过/失败/取消/超时、"
            "商户名称与国家、交易金额。"
            "BU 问'这笔消费是不是本人''是否走了 3DS''有没有可疑/盗刷交易'时必用。"
            "建议先 query_bu_card 拿到 card_id。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入
                "card_id": {"type": "string", "description": "按卡 id 过滤该卡的授权记录"},
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
