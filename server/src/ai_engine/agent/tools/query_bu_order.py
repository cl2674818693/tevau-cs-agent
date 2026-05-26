from typing import Any

from ai_engine.agent.tools.base import Tool, label, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_order_info（B 端订单），按 tenant_id 隔离。
# third_card_id 用于关联异常表（异常表 card_id 是三方卡 UUID）。
SQL = """
SELECT order_sn, trade_order_sn, order_type, status, trade_amount, fee,
       channel_amount, channel_fee, currency, create_time, end_time, remark,
       third_card_id
FROM t_nexus_order_info
WHERE tenant_id=%s AND del_flag=0
ORDER BY create_time DESC
"""

# 失败原因不在订单主表，在 t_nexus_trans_exception（卡级异常）。
# 该表无 order_sn/trade_order_sn 关联键，trans_id 是卡网 txId（与订单号不匹配）。
# 唯一可用且带租户隔离的关联：tenant_id + card_id，订单侧用 third_card_id 对应异常表 card_id。
# 因此 failure_reason 是"该卡近期异常线索"（卡级），非订单级精确归因。
EXC_SQL = """
SELECT reason, error_trans_code, trans_type, exception_type, create_time
FROM t_nexus_trans_exception
WHERE tenant_id=%s AND card_id=%s AND del_flag=0
ORDER BY create_time DESC
"""

# order_type 枚举：以真实库列注释 + 后端 OrderTypeEnum.java 双重核对。
# 真实库 GROUP BY 出现的取值：1,2,4,6,8,9,13,14,16,17,18,19,20,21,22,23,24,25,26,27,28,99
# 后端枚举覆盖 1-14,16-26（无 15/27/28/99）；列注释明确 25=提币订单 26=币种兑换订单。
_ORDER_TYPE: dict[Any, str] = {
    1: "开卡订单",
    2: "卡充值订单",
    3: "卡提现订单",
    4: "销卡订单",
    5: "卡冻结",
    6: "卡解冻",
    7: "卡激活",
    8: "绑定卡",
    9: "卡月费",
    10: "开卡奖励",
    11: "开卡订单CID",
    12: "开卡账户BAC",
    13: "企业账户ENT",
    14: "KYC提交扣费",
    16: "调账订单",
    17: "KYC月费",
    18: "交易订单",
    19: "预付款账户充值订单",
    20: "3DS次数扣费订单",
    21: "3DS月费扣费订单",
    22: "物流费用",
    23: "批量出卡记录订单",
    24: "申诉/退单",
    25: "提币订单",
    26: "币种兑换订单",
}
# status 枚举：列注释 + GROUP BY 双核对。0,1,2,3,4,5,6 均真实存在（6=审核中，10 行真实数据）。
_STATUS: dict[Any, str] = {
    0: "待处理",
    1: "已完成",
    2: "已取消(已关闭)",
    3: "已退款",
    4: "失败",
    5: "部分退款",
    6: "审核中",
}
# 订单状态=失败时才去查卡级异常原因
_FAILED_STATUS = 4


async def _failure_reason(db: Any, tenant_id: str, third_card_id: Any) -> dict[str, Any] | None:
    """失败订单的卡级异常线索（tenant_id 隔离 + card_id 关联）。无 third_card_id 或无异常则 None。"""
    if not third_card_id or third_card_id in ("", "-"):
        return None
    rows = await db.fetch_all(EXC_SQL, (tenant_id, third_card_id), limit=3)
    if not rows:
        return None
    top = rows[0]
    return {
        "note": "卡级异常线索（按租户+卡号关联，非订单级精确归因）",
        "reason": top.get("reason"),
        "error_trans_code": top.get("error_trans_code"),
        "trans_type": top.get("trans_type"),
        "exception_count": len(rows),
    }


async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU(租户)最近订单（开卡/充值/提现/销卡等及状态）。BU 问订单状态/对账/某笔为何失败时用。"""
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)
    orders = []
    for r in rows:
        o: dict[str, Any] = {
            "order_sn": r.get("order_sn"),
            "trade_order_sn": r.get("trade_order_sn"),
            "order_type": label(_ORDER_TYPE, r.get("order_type")),
            "status": label(_STATUS, r.get("status")),
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
        if r.get("status") == _FAILED_STATUS:
            o["failure_reason"] = await _failure_reason(db, tenant_id, r.get("third_card_id"))
        orders.append(o)
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
