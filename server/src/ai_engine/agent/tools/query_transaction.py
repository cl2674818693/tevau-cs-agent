from typing import Any

from ai_engine.agent.tools.base import Tool, register, label
from ai_engine.persistence.business_db import get_db

CARD_SQL = """
SELECT r.type, r.digest, r.status, r.currency, r.trade_amount, r.income_amount,
       r.out_amount, r.fee, r.merchant_name, r.remark, r.order_id, r.pay_type,
       COALESCE(r.recharge_time, r.create_time) AS tx_time,
       c.card_number
FROM t_tevaupay_card_recharge_records r
LEFT JOIN t_tevaupay_bank_card_user c ON c.three_card_id = r.card_id
WHERE r.user_id=%s AND r.status IN (3,4,8) AND r.type NOT IN (25,22)
ORDER BY r.date_time_stamp DESC
"""
WALLET_SQL = """
SELECT type, transaction_status, fund_flow, trade_amount, fee, currency, create_time
FROM t_tevaupay_transaction_wallet_records
WHERE user_id=%s ORDER BY create_time DESC
"""

_CARD_TYPE: dict[Any, str] = {1: "充值卡", 2: "提现卡", 3: "申请卡", 4: "卡消费", 5: "ATM取款", 6: "卡销户",
    7: "开卡充值手续费", 8: "销卡", 9: "卡冻结", 10: "卡解冻", 11: "退款", 12: "卡消费处理费",
    13: "授权查询", 14: "冲正", 15: "交易处理费冲正", 16: "交易", 17: "交易处理费", 18: "网上支付",
    19: "刷卡支付", 20: "非接触支付", 21: "TXN已退款", 22: "TXN退款处理", 23: "未知交易",
    24: "拒付(ChargeBack)", 25: "卡激活剩余余额充值", 26: "其他交易", 27: "未知卡交易",
    28: "平台卡扣费", 29: "奖励", 30: "拒付", 31: "不活跃扣费"}
_CARD_STATUS: dict[Any, str] = {-1: "未知", 1: "待处理", 2: "处理中", 3: "成功", 4: "失败", 5: "待退款",
    6: "三方返回失败", 7: "已授权", 8: "已结算", 9: "已取消", 10: "已拒绝", 11: "对账退款中"}
_CURRENCY: dict[Any, str] = {1: "USDT", 2: "USD", 3: "ARB_ETH", 4: "BNB", 5: "TRX", 6: "EUR", 7: "BTCW",
    8: "HKD", 9: "CNY", 12: "IDR", 15: "XUSD"}
_DIGEST: dict[Any, str] = {1: "入账", 2: "出账"}
_PAY_TYPE: dict[Any, str] = {1: "宝付", 2: "easyeuro", 3: "reap", 4: "sx"}
_WALLET_TYPE: dict[Any, str] = {1: "充币", 2: "提币", 3: "转账", 4: "调账", 5: "归集", 6: "开卡", 7: "卡充值", 9: "转账(收)"}
_WALLET_STATUS: dict[Any, str] = {1: "待处理", 2: "处理中", 3: "成功", 4: "失败"}
_FLOW: dict[Any, str] = {1: "入账", 2: "出账"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户的卡交易流水（消费/奖励/退款等，APP首页"最近交易"同源）与钱包充提流水。"""
    db = get_db("unlimitpay")
    card_rows = await db.fetch_all(CARD_SQL, (user_id,), limit=20)
    wallet_rows = await db.fetch_all(WALLET_SQL, (user_id,), limit=20)
    cards = [{
        "type": label(_CARD_TYPE, r.get("type")),
        "flow": label(_DIGEST, r.get("digest")),
        "status": label(_CARD_STATUS, r.get("status")),
        "currency": label(_CURRENCY, r.get("currency")),
        "amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
        "fee": str(r["fee"]) if r.get("fee") is not None else None,
        "merchant": r.get("merchant_name"),
        "remark": r.get("remark"),
        "order_id": r.get("order_id"),
        "channel": label(_PAY_TYPE, r.get("pay_type")),
        "card_number": r.get("card_number"),
        "time": str(r["tx_time"]) if r.get("tx_time") else None,
    } for r in card_rows]
    wallets = [{
        "type": label(_WALLET_TYPE, r.get("type")),
        "status": label(_WALLET_STATUS, r.get("transaction_status")),
        "flow": label(_FLOW, r.get("fund_flow")),
        "amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
        "currency": label(_CURRENCY, r.get("currency")),
        "time": str(r["create_time"]) if r.get("create_time") else None,
    } for r in wallet_rows]
    return {
        "card_transactions": cards, "card_count": len(cards),
        "wallet_flows": wallets, "wallet_count": len(wallets),
        "note": "card_transactions 是 APP 首页可见的卡交易（消费/奖励/退款）；"
                "wallet_flows 是钱包充提。两者都为空才说明该用户暂无交易。",
    }


register(Tool(
    name="query_transaction",
    description="查询当前用户的卡交易流水（消费/奖励/退款/不活跃扣费等，与 APP 首页'最近交易'同源）"
                "及钱包充提流水。用户问'我的交易/流水/奖励''为什么扣款''转账到账没'时用。",
    input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}, "required": []},
    handler=run, requires_subject_id=True, subject_field="user_id", supports_unmask=False,
))
