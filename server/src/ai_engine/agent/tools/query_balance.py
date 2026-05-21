from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_account_currency_user（用户币种总账户），按 user_id 隔离
# account_type=0 即用户总钱包；money_type 1 现金 / 2 在途
SQL = """
SELECT money_type, currency, total_count, status, account_no
FROM t_tevaupay_account_currency_user
WHERE user_id=%s AND account_type=0
ORDER BY currency, money_type
"""

_MONEY_TYPE: dict[Any, str] = {1: "现金", 2: "在途"}
_CURRENCY: dict[Any, str] = {1: "USDT", 2: "USD"}
_STATUS: dict[Any, str] = {0: "正常", 1: "锁定"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户总钱包各币种余额（现金/在途）。用户问'我的余额''钱包还有多少'时用。"""
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=50)
    balances = [
        {
            "currency": _CURRENCY.get(r.get("currency"), r.get("currency")),
            "money_type": _MONEY_TYPE.get(r.get("money_type"), r.get("money_type")),
            "amount": str(r["total_count"]) if r.get("total_count") is not None else None,
            "status": _STATUS.get(r.get("status"), r.get("status")),
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
