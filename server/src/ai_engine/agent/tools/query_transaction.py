from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_transaction_wallet_records（钱包交易流水），按 user_id 隔离
SQL = """
SELECT type, transaction_status, fund_flow, trade_amount, income_amount, out_amount, fee,
       currency, order_id, business_no, remark, transaction_hash, create_time
FROM t_tevaupay_transaction_wallet_records
WHERE user_id=%s
ORDER BY create_time DESC
"""

_TYPE: dict[Any, str] = {
    1: "充币",
    2: "提币",
    3: "转账",
    4: "调账",
    5: "归集",
    6: "开卡",
    7: "卡充值",
    9: "转账(收)",
}
_STATUS: dict[Any, str] = {1: "待处理", 2: "处理中", 3: "成功", 4: "失败"}
_FLOW: dict[Any, str] = {1: "入账", 2: "出账"}
_CURRENCY: dict[Any, str] = {1: "USDT", 2: "USD"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户最近钱包交易流水（充值/提现/转账等及成功失败状态）。用户问转账/到账/交易失败时用。"""
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=20)
    txns = []
    for r in rows:
        item = {
            "type": _TYPE.get(r.get("type"), r.get("type")),
            "status": _STATUS.get(r.get("transaction_status"), r.get("transaction_status")),
            "flow": _FLOW.get(r.get("fund_flow")),
            "amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
            "fee": str(r["fee"]) if r.get("fee") is not None else None,
            "currency": _CURRENCY.get(r.get("currency"), r.get("currency")),
            "order_id": r.get("order_id"),
            "business_no": r.get("business_no"),
            "remark": r.get("remark"),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        if unmask:
            item["transaction_hash"] = r.get("transaction_hash")
        txns.append(item)
    return {"transactions": txns, "count": len(txns), "unmasked": unmask}


register(
    Tool(
        name="query_transaction",
        description=(
            "查询当前用户最近的钱包交易流水（充值/提现/转账/调账等，含成功/失败状态）。"
            "用户问'转账成功没''钱到账了吗''为什么交易失败'时用。"
        ),
        input_schema={
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="user_id",
        supports_unmask=True,
    )
)
