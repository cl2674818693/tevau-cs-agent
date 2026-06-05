from typing import Any

from ai_engine.agent.tools.base import Tool, label, register, scope_note
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test 理财（financing）相关三张主表，按 user_id 隔离：
#   t_tevaupay_financing_user_account          用户理财账户（按币种、现金/在途）
#   t_tevaupay_financing_user_product_account  用户每产品持仓（累计申购/赎回/盈利/分红）
#   t_tevaupay_financing_user_order            申购/赎回/转入/转出/收益等订单
# 货币与 query_balance 同源 CurrencyEnum；状态/类型枚举来自后端 tevaupay-common。

SQL_ACCOUNTS = """
SELECT account_no, currency, account_type, money_type, balance, status
FROM t_tevaupay_financing_user_account
WHERE user_id=%s AND account_type=2
ORDER BY currency, money_type
"""

SQL_PRODUCT_POSITIONS = """
SELECT pa.prod_id, p.product_name, p.product_code, pa.product_tag, pa.money_type,
       pa.balance, pa.total_profit, pa.total_dividend, pa.total_subscribe, pa.total_redeem,
       pa.update_time
FROM t_tevaupay_financing_user_product_account pa
LEFT JOIN t_tevaupay_financing_product p ON p.id = pa.prod_id
WHERE pa.user_id=%s AND pa.account_type=5
ORDER BY pa.prod_id, pa.money_type
"""

SQL_RECENT_ORDERS = """
SELECT o.order_id, o.platform_order_id, o.prod_id, p.product_name,
       o.order_type, o.fund_flow, o.amount, o.fee, o.order_status,
       o.wallet_order_id, o.profit_date, o.create_time, o.remark
FROM t_tevaupay_financing_user_order o
LEFT JOIN t_tevaupay_financing_product p ON p.id = o.prod_id
WHERE o.user_id=%s
ORDER BY o.create_time DESC
LIMIT %s
"""

# 与 query_balance 同源 CurrencyEnum
_CURRENCY: dict[Any, str] = {
    0: "UNKNOWN", 1: "USDT", 2: "USD", 3: "ARB_ETH", 4: "BNB", 5: "TRX",
    6: "EUR", 7: "BTCW", 8: "HKD", 9: "CNY", 12: "IDR", 15: "XUSD",
}
_MONEY_TYPE: dict[Any, str] = {1: "现金", 2: "在途"}
_ACCOUNT_STATUS: dict[Any, str] = {1: "可用", 2: "不可用"}
# t_tevaupay_financing_user_product_account.product_tag / product.product_tag
# FinancingProductTagEnum
_PRODUCT_TAG: dict[Any, str] = {1: "标准理财", 2: "Vault 理财"}
# FinancingOrderTypeEnum（后端 tevaupay-common）。10/11/13/15 后端枚举未定义到，
# 留给 base.label() 显式标注"未知(原值)"，不静默吞。
_ORDER_TYPE: dict[Any, str] = {
    1: "用户认购",
    2: "用户赎回",
    3: "钱包转入理财",
    4: "理财转出钱包",
    5: "平台收益",
    6: "用户收益结算",
    7: "平台支出",
    8: "平台产品收益",
    9: "平台产品支出",
}
# FundFlowEnum
_FUND_FLOW: dict[Any, str] = {1: "入账", 2: "出账"}
# 订单状态：表注释明确 2/3/4，其他值同样交给 label()
_ORDER_STATUS: dict[Any, str] = {2: "进行中", 3: "成功", 4: "失败"}


async def run(user_id: str, recent_orders_limit: int = 20, unmask: bool = False) -> dict[str, Any]:
    """查当前用户的理财账户余额、各产品持仓、最近申购/赎回/收益订单。
    用户问"我的理财还有多少""昨天收益多少""为什么申购/赎回失败"时用。"""
    db = get_db("unlimitpay")
    limit = max(1, min(int(recent_orders_limit or 20), 100))

    account_rows = await db.fetch_all(SQL_ACCOUNTS, (user_id,), limit=50)
    position_rows = await db.fetch_all(SQL_PRODUCT_POSITIONS, (user_id,), limit=100)
    order_rows = await db.fetch_all(SQL_RECENT_ORDERS, (user_id, limit), limit=limit)

    accounts = [
        {
            "account_no": r.get("account_no") if unmask else None,
            "currency": label(_CURRENCY, r.get("currency")),
            "money_type": label(_MONEY_TYPE, r.get("money_type")),
            "balance": str(r["balance"]) if r.get("balance") is not None else None,
            "status": label(_ACCOUNT_STATUS, r.get("status")),
        }
        for r in account_rows
    ]
    positions = [
        {
            "prod_id": r.get("prod_id"),
            "product_name": r.get("product_name"),
            "product_code": r.get("product_code"),
            "product_tag": label(_PRODUCT_TAG, r.get("product_tag")),
            "money_type": label(_MONEY_TYPE, r.get("money_type")),
            "balance": str(r["balance"]) if r.get("balance") is not None else None,
            "total_profit": str(r["total_profit"]) if r.get("total_profit") is not None else None,
            "total_dividend": str(r["total_dividend"]) if r.get("total_dividend") is not None else None,
            "total_subscribe": str(r["total_subscribe"]) if r.get("total_subscribe") is not None else None,
            "total_redeem": str(r["total_redeem"]) if r.get("total_redeem") is not None else None,
            "update_time": str(r["update_time"]) if r.get("update_time") else None,
        }
        for r in position_rows
    ]
    orders = [
        {
            "order_id": r.get("order_id"),
            "platform_order_id": r.get("platform_order_id"),
            "prod_id": r.get("prod_id"),
            "product_name": r.get("product_name"),
            "order_type": label(_ORDER_TYPE, r.get("order_type")),
            "fund_flow": label(_FUND_FLOW, r.get("fund_flow")),
            "amount": str(r["amount"]) if r.get("amount") is not None else None,
            "fee": str(r["fee"]) if r.get("fee") is not None else None,
            "order_status": label(_ORDER_STATUS, r.get("order_status")),
            "wallet_order_id": r.get("wallet_order_id"),
            "profit_date": r.get("profit_date"),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
            "remark": r.get("remark"),
        }
        for r in order_rows
    ]
    return {
        "accounts": accounts,
        "product_positions": positions,
        "recent_orders": orders,
        "recent_orders_limit": limit,
        "scope_note": scope_note(
            "理财(financing)账户、产品持仓与申购/赎回/收益订单",
            "用户认购/赎回/转入转出/每日收益结算/各产品累计盈利分红",
            "证券股票订单(tevaufinance-investment)、钱包币种余额、卡片消费",
        ),
        "unmasked": unmask,
    }


register(
    Tool(
        name="query_financing",
        description=(
            "查询当前用户的理财(financing)账户余额、各产品持仓与最近申购/赎回/收益订单。"
            "用户问'我的理财还有多少''昨天收益''为什么申购/赎回失败''钱包和理财怎么转账'时用。"
            "注意：证券股票/持仓走 APP 证券页面，不在本工具范围。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "recent_orders_limit": {
                    "type": "integer",
                    "description": "最近订单条数，默认 20，最大 100",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="user_id",
        supports_unmask=True,
    )
)
