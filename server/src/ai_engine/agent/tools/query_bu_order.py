from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_order_info（B 端订单），按 tenant_id 隔离
SQL = """
SELECT order_sn, trade_order_sn, order_type, status, trade_amount, fee,
       channel_amount, channel_fee, currency, create_time, end_time, remark
FROM t_nexus_order_info
WHERE tenant_id=%s AND del_flag=0
ORDER BY create_time DESC
"""

_ORDER_TYPE: dict[Any, str] = {
    1: "开卡",
    2: "卡充值",
    3: "卡提现",
    4: "销卡",
    5: "卡冻结",
    6: "卡解冻",
    7: "卡激活",
    8: "绑定卡",
    9: "月费",
    10: "开卡奖励",
    14: "KYC提交扣费",
    16: "调账",
    18: "交易",
    19: "预付款账户充值",
    25: "提币",
    26: "币种兑换",
}
_STATUS: dict[Any, str] = {
    0: "待处理",
    1: "已完成",
    2: "已取消",
    3: "已退款",
    4: "失败",
    5: "部分退款",
    6: "审核中",
}


async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU(租户)最近订单（开卡/充值/提现/销卡等及状态）。BU 问订单状态/对账时用。"""
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)
    orders = [
        {
            "order_sn": r.get("order_sn"),
            "trade_order_sn": r.get("trade_order_sn"),
            "order_type": _ORDER_TYPE.get(r.get("order_type"), r.get("order_type")),
            "status": _STATUS.get(r.get("status"), r.get("status")),
            "trade_amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
            "fee": str(r["fee"]) if r.get("fee") is not None else None,
            "channel_amount": str(r["channel_amount"])
            if r.get("channel_amount") is not None
            else None,
            "currency": r.get("currency"),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
            "end_time": str(r["end_time"]) if r.get("end_time") else None,
            "remark": r.get("remark"),
        }
        for r in rows
    ]
    return {"orders": orders, "count": len(orders)}


register(
    Tool(
        name="query_bu_order",
        description=(
            "查询当前 BU(企业租户)最近的订单与状态（开卡/充值/提现/销卡等）。"
            "BU 问'订单到哪了''对账''某笔订单为什么失败'时用。"
        ),
        input_schema={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}},  # router 强制注入
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
    )
)
