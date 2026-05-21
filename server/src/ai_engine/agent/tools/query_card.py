from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_card_no
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_bank_card_user（C 端 APP 卡主表），按 user_id 隔离
SQL = """
SELECT id, card_number, card_status, card_status_description, card_balance, card_currency,
       card_type, expiry_date, reject_reason, cancel_card_reason, card_alias_name,
       active_time, create_time
FROM t_tevaupay_bank_card_user
WHERE user_id=%s AND del=0
ORDER BY create_time DESC
"""

# card_status 字典（见列注释）
_STATUS: dict[Any, str] = {
    100: "待申请",
    0: "开卡成功",
    1: "已注销",
    2: "已锁定（仅客户可操作）",
    3: "申请中",
    4: "开卡失败",
    5: "注销中",
    6: "注销失败",
    7: "已冻结（仅管理员可操作）",
    8: "制作中",
    9: "卡片冻结",
    10: "已过期",
    11: "取消开卡",
    12: "已发货",
}
_CURRENCY: dict[Any, str] = {1: "USDT", 2: "USD", 3: "ETH"}
_CARD_TYPE: dict[Any, str] = {1: "实体卡", 2: "虚拟卡"}


def _card_view(row: dict[str, Any], unmask: bool) -> dict[str, Any]:
    cn = row.get("card_number")
    status = row.get("card_status")
    return {
        "card_id": row["id"],
        "card_no": cn if unmask else mask_card_no(cn),
        "status_code": status,
        "status": _STATUS.get(status, f"未知({status})"),
        "status_desc": row.get("card_status_description"),
        "balance": str(row["card_balance"]) if row.get("card_balance") is not None else None,
        "currency": _CURRENCY.get(row.get("card_currency"), row.get("card_currency")),
        "card_type": _CARD_TYPE.get(row.get("card_type")),
        "expiry_date": row.get("expiry_date"),
        "reject_reason": row.get("reject_reason"),
        "cancel_card_reason": row.get("cancel_card_reason"),
        "alias": row.get("card_alias_name"),
        "create_time": str(row["create_time"]) if row.get("create_time") else None,
    }


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户名下所有卡的状态（锁定/冻结看 status；卡号脱敏，unmask 仅 engineer 代查）。"""
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=20)
    return {"cards": [_card_view(r, unmask) for r in rows], "count": len(rows), "unmasked": unmask}


register(
    Tool(
        name="query_card",
        description=(
            "查询当前用户名下所有银行卡的状态与信息（卡号脱敏）。"
            "用户问'我的卡为什么被锁/冻结''卡状态''卡余额'时用。"
            "锁定/冻结看 status，原因看 status_desc/reject_reason。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},  # router 强制注入当前登录用户
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="user_id",
        supports_unmask=True,
    )
)
