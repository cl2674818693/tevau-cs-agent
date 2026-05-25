from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 卡账户交易明细 t_nexus_card_account_detail_0..9（分表，无 card_id 列，按 account_number 关联）。
# 关联链：卡(card_id/PAN) →(t_nexus_bank_card_company.account_num)→ detail.account_number。
# 这是"卡余额对不上/变少/退款没到"的逐笔对账台账：每行带交易前后余额(begin/end)。
_CARD_SQL = """
SELECT account_num, user_id
FROM t_nexus_bank_card_company
WHERE tenant_id=%s AND del_flag=0 AND {filter}=%s
LIMIT 1
"""
_DETAIL_COLS = (
    "accounting_type, trade_status, detail_type, begin_amount, end_amount, "
    "income_amount, out_amount, trade_currency, trade_sn, ref_order_sn, digest, "
    "trade_date, create_time"
)

_ACCOUNTING: dict[Any, str] = {
    1: "充值",
    2: "开卡",
    3: "销卡",
    4: "授权交易",
    5: "退款",
    6: "结算",
    7: "新订单退款",
    8: "开户",
    9: "交易退款",
    10: "部分取消",
    11: "全额取消",
    12: "卡余额调账",
}
_TRADE_STATUS: dict[Any, str] = {1: "成功", 2: "失败", 3: "待执行"}
_DETAIL_TYPE: dict[Any, str] = {1: "入账", 2: "出账"}


async def run(
    tenant_id: str,
    card_id: str | None = None,
    card_number: str | None = None,
    unmask: bool = False,
) -> dict[str, Any]:
    """查某张卡的逐笔交易台账（充值/授权/退款/调账等，含每笔交易前后余额）。卡余额对不上/退款没到对账用。"""
    if not tenant_id:
        return {"ledger": [], "count": 0, "note": "缺少 tenant 身份"}
    db = get_db("nexus")
    if card_id:
        card = await db.fetch_one(_CARD_SQL.format(filter="card_id"), (tenant_id, card_id))
    elif card_number:
        digits = "".join(ch for ch in card_number if ch.isdigit())
        card = await db.fetch_one(_CARD_SQL.format(filter="card_number"), (tenant_id, digits))
    else:
        return {"ledger": [], "count": 0, "note": "需提供 card_id 或 card_number"}
    if not card or not card.get("account_num"):
        return {"ledger": [], "count": 0, "note": "未找到该卡或卡无现金账户"}

    account = card["account_num"]
    # 明细分 0..9 表，按 account_number 跨表 UNION（各表 tenant_id 仍参与隔离）
    parts = [
        # 仅拼接常量列名和分表序号 i(int)，值仍走参数化，无注入风险
        f"SELECT {_DETAIL_COLS} FROM t_nexus_card_account_detail_{i} "  # noqa: S608
        "WHERE tenant_id=%s AND account_number=%s AND del_flag=0"
        for i in range(10)
    ]
    sql = "(" + ") UNION ALL (".join(parts) + ") ORDER BY create_time DESC"
    params = (tenant_id, account) * 10
    rows = await db.fetch_all(sql, params, limit=30)
    ledger = [
        {
            "type": _ACCOUNTING.get(r.get("accounting_type"), r.get("accounting_type")),
            "status": _TRADE_STATUS.get(r.get("trade_status"), r.get("trade_status")),
            "flow": _DETAIL_TYPE.get(r.get("detail_type")),
            "begin_amount": str(r["begin_amount"]) if r.get("begin_amount") is not None else None,
            "end_amount": str(r["end_amount"]) if r.get("end_amount") is not None else None,
            "income": r.get("income_amount"),
            "out": r.get("out_amount"),
            "currency": r.get("trade_currency"),
            "trade_sn": r.get("trade_sn"),
            "ref_order_sn": r.get("ref_order_sn"),
            "digest": r.get("digest"),
            "trade_date": r.get("trade_date"),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        for r in rows
    ]
    return {"ledger": ledger, "count": len(ledger), "account": account}


register(
    Tool(
        name="query_card_ledger",
        description=(
            "查询某张卡的逐笔交易台账（t_nexus_card_account_detail）：充值/授权交易/退款/调账等，"
            "每行含交易前后余额(begin/end)、入账/出账、关联订单号。"
            "BU 问'卡余额对不上''余额变少''退款有没有入账''钱去哪了'时用，可逐笔核对余额变动。"
            "传 card_id（CIDV/CIDP）或 card_number（完整卡号 PAN）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入
                "card_id": {"type": "string", "description": "卡 id（CIDV/CIDP…）"},
                "card_number": {"type": "string", "description": "完整卡号 PAN"},
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
