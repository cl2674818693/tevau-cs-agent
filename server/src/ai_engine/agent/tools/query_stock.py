from typing import Any

from ai_engine.agent.tools.base import Tool, gated, register, scope_note
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test 证券（tevaufinance-investment）相关表，按 user_id 隔离：
#   t_tevaufinance_account             股票账户（现金/可用/冻结/未结算）
#   t_tevaufinance_positions           持仓汇总（每只股票一行：数量/成本/累计盈亏）
#   t_tevaufinance_order               股票订单（买卖方向/状态/价格/成交/手续费）
#   t_tevaufinance_stock_watchlist     用户自选股
# 枚举字段全部是后端业务字符串（CASH/USDT/BUY/SELL/LIMIT/MARKET/
# PENDING/SUBMITTED/LIVE/PARTIALLY_FILLED/FILLED/INACTIVE/FAILED/CANCELLED 等），
# 直接透传给 AI 即可，不再做中文映射。

SQL_ACCOUNTS = """
SELECT account_no, account_type, currency, cash_balance, freeze_balance,
       available_balance, unsettled_balance, status, create_time
FROM t_tevaufinance_account
WHERE user_id=%s AND del=0
ORDER BY currency, account_no
"""

SQL_POSITIONS = """
SELECT symbol, status, sec_type, currency,
       quantity, available_quantity, unsettled_quantity, frozen_quantity,
       average_buy_price, open_price, total_cost,
       total_sold_quantity, total_sold_amount, total_realized_pnl,
       total_buy_plat_fee, total_sell_plat_fee,
       open_time, close_time, update_time
FROM t_tevaufinance_positions
WHERE user_id=%s AND del=0
ORDER BY (status='CLOSE'), update_time DESC
"""

SQL_RECENT_ORDERS = """
SELECT order_no, symbol, sec_type, order_type, side, market, exchange, broker,
       price, quantity, status, cancel_status, modify_status,
       filled_quantity, cancelled_quantity, average_filled_price,
       commission_fee, plat_fee, estimate_amount, amount, trade_amount,
       time_in_force, time_frame, risk_dispose_action, risk_reason,
       remark, create_time, update_time, submitted_to_broker_at
FROM t_tevaufinance_order
WHERE user_id=%s AND del=0
ORDER BY create_time DESC
LIMIT %s
"""

SQL_WATCHLIST = """
SELECT symbol, sort_order, create_time
FROM t_tevaufinance_stock_watchlist
WHERE user_id=%s AND deleted=0
ORDER BY sort_order ASC
LIMIT %s
"""


def _dec(row: dict, key: str) -> str | None:
    v = row.get(key)
    return str(v) if v is not None else None


def _dt(row: dict, key: str) -> str | None:
    v = row.get(key)
    return str(v) if v else None


async def run(
    user_id: str,
    recent_orders_limit: int = 20,
    watchlist_limit: int = 30,
    unmask: bool = False,
) -> dict[str, Any]:
    """查当前用户的证券（股票）账户、持仓、最近订单、自选股。
    用户问"我的股票账户余额""持仓多少""订单成交了吗""我的自选股"时用。
    注意：行情/K线/分时数据是公开行情，本工具不返回；理财(financing)走 query_financing。"""
    db = get_db("unlimitpay")
    order_lim = max(1, min(int(recent_orders_limit or 20), 100))
    watch_lim = max(1, min(int(watchlist_limit or 30), 100))

    acc_rows = await db.fetch_all(SQL_ACCOUNTS, (user_id,), limit=50)
    pos_rows = await db.fetch_all(SQL_POSITIONS, (user_id,), limit=200)
    ord_rows = await db.fetch_all(SQL_RECENT_ORDERS, (user_id, order_lim), limit=order_lim)
    wch_rows = await db.fetch_all(SQL_WATCHLIST, (user_id, watch_lim), limit=watch_lim)

    accounts = [
        {
            "account_no": r.get("account_no") if unmask else None,
            "account_type": r.get("account_type"),  # CASH 等
            "currency": r.get("currency"),
            "cash_balance": _dec(r, "cash_balance"),
            "available_balance": _dec(r, "available_balance"),
            "freeze_balance": _dec(r, "freeze_balance"),
            "unsettled_balance": _dec(r, "unsettled_balance"),
            "status": r.get("status"),  # NORMAL/FREEZE/CLOSE
            "create_time": _dt(r, "create_time"),
        }
        for r in acc_rows
    ]
    positions = [
        {
            "symbol": r.get("symbol"),
            "status": r.get("status"),  # NONE/PARTIALLY/CLOSE
            "sec_type": r.get("sec_type"),
            "currency": r.get("currency"),
            "quantity": _dec(r, "quantity"),
            "available_quantity": _dec(r, "available_quantity"),
            "unsettled_quantity": _dec(r, "unsettled_quantity"),
            "frozen_quantity": _dec(r, "frozen_quantity"),
            "average_buy_price": _dec(r, "average_buy_price"),
            "open_price": _dec(r, "open_price"),
            "total_cost": _dec(r, "total_cost"),
            "total_sold_quantity": _dec(r, "total_sold_quantity"),
            "total_sold_amount": _dec(r, "total_sold_amount"),
            "total_realized_pnl": _dec(r, "total_realized_pnl"),
            "total_buy_plat_fee": _dec(r, "total_buy_plat_fee"),
            "total_sell_plat_fee": _dec(r, "total_sell_plat_fee"),
            "open_time": _dt(r, "open_time"),
            "close_time": _dt(r, "close_time"),
            "update_time": _dt(r, "update_time"),
        }
        for r in pos_rows
    ]
    orders = [
        {
            "order_no": r.get("order_no"),
            "symbol": r.get("symbol"),
            "sec_type": r.get("sec_type"),
            "order_type": r.get("order_type"),  # LIMIT/MARKET
            "side": r.get("side"),  # BUY/SELL
            "market": r.get("market"),
            "exchange": r.get("exchange"),
            "broker": r.get("broker"),
            "price": _dec(r, "price"),
            "quantity": _dec(r, "quantity"),
            "status": r.get("status"),
            # PENDING/SUBMITTED/LIVE/PARTIALLY_FILLED/FILLED/INACTIVE/FAILED/CANCELLED
            "cancel_status": r.get("cancel_status"),  # NONE/PENDING/CANCELLED/FAILED
            "modify_status": r.get("modify_status"),  # NONE/PENDING/REPLACED/FAILED
            "filled_quantity": _dec(r, "filled_quantity"),
            "cancelled_quantity": _dec(r, "cancelled_quantity"),
            "average_filled_price": _dec(r, "average_filled_price"),
            "commission_fee": _dec(r, "commission_fee"),
            "plat_fee": _dec(r, "plat_fee"),
            "estimate_amount": _dec(r, "estimate_amount"),
            "amount": _dec(r, "amount"),
            "trade_amount": _dec(r, "trade_amount"),
            "time_in_force": r.get("time_in_force"),
            "time_frame": r.get("time_frame"),
            "risk_dispose_action": r.get("risk_dispose_action"),  # NONE/REJECT/ALERT 行动分类可保留
            # risk_reason 原文含风控触发条件/阈值，直给用户=教绕过，默认 gate
            "risk_reason": gated(r.get("risk_reason"), unmask),
            "remark": r.get("remark"),
            "submitted_to_broker_at": _dt(r, "submitted_to_broker_at"),
            "create_time": _dt(r, "create_time"),
            "update_time": _dt(r, "update_time"),
        }
        for r in ord_rows
    ]
    watchlist = [
        {
            "symbol": r.get("symbol"),
            "sort_order": r.get("sort_order"),
            "create_time": _dt(r, "create_time"),
        }
        for r in wch_rows
    ]
    return {
        "accounts": accounts,
        "positions": positions,
        "recent_orders": orders,
        "recent_orders_limit": order_lim,
        "watchlist": watchlist,
        "watchlist_limit": watch_lim,
        "scope_note": scope_note(
            "证券（股票）账户、持仓、最近订单与自选股",
            "股票现金账户、每只股票持仓与累计盈亏、最近 N 单买卖订单状态、自选股列表",
            "行情/K 线/分时数据（公开行情走 APP 行情页面）、理财(走 query_financing)、钱包币种余额(走 query_balance)",
        ),
        "unmasked": unmask,
    }


register(
    Tool(
        name="query_stock",
        description=(
            "查询当前用户的证券（股票）账户余额、持仓汇总、最近订单状态与自选股列表。"
            "用户问'股票账户多少钱''持仓多少股''订单成交了吗''为什么下单失败''我的自选股'时用。"
            "注意：行情 / K 线 / 分时是公开数据走 APP 行情页面，本工具不返回；"
            "理财申购赎回走 query_financing，不在本工具范围。"
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
                "watchlist_limit": {
                    "type": "integer",
                    "description": "自选股条数，默认 30，最大 100",
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
