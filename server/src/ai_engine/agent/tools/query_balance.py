from typing import Any

from ai_engine.agent.tools.base import Tool, label, register
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_account_currency_user（用户币种总账户），按 user_id 隔离
# account_type=0 即用户总钱包；money_type 1 现金 / 2 在途
# 同一 user_id 可跨 plat_source 多平台各有账户，需带出 plat_source 区分
SQL = """
SELECT money_type, currency, total_count, status, account_no, plat_source
FROM t_tevaupay_account_currency_user
WHERE user_id=%s AND account_type=0
ORDER BY plat_source, currency, money_type
"""

_MONEY_TYPE: dict[Any, str] = {1: "现金", 2: "在途"}
# CurrencyEnum（后端 tevaupay-common）；库里另存在 currency=11 但 enum 未定义，故由 label 标注为 未知(11)
_CURRENCY: dict[Any, str] = {
    0: "UNKNOWN", 1: "USDT", 2: "USD", 3: "ARB_ETH", 4: "BNB", 5: "TRX",
    6: "EUR", 7: "BTCW", 8: "HKD", 9: "CNY", 12: "IDR", 15: "XUSD",
}
_STATUS: dict[Any, str] = {0: "正常", 1: "冻结"}
# PlatSourceEnum（后端 tevaupay-common）：无 4
_PLAT: dict[Any, str] = {1: "tevau", 2: "unlimitpay", 3: "skydaopay", 5: "fiatpay", 6: "mall"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户总钱包各币种余额（现金/在途）。用户问'我的余额''钱包还有多少'时用。"""
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=50)
    balances = [
        {
            "currency": label(_CURRENCY, r.get("currency")),
            "money_type": label(_MONEY_TYPE, r.get("money_type")),
            "amount": str(r["total_count"]) if r.get("total_count") is not None else None,
            "status": label(_STATUS, r.get("status")),
            "plat_source": label(_PLAT, r.get("plat_source")),
            "account_no": r.get("account_no") if unmask else None,
        }
        for r in rows
    ]
    return {"balances": balances, "count": len(balances), "unmasked": unmask}


register(
    Tool(
        name="query_balance",
        description="查询当前用户钱包各币种余额（现金/在途）。用户问余额、钱包金额时用。",
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
