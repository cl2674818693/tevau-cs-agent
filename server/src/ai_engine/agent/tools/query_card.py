from typing import Any

from ai_engine.agent.tools.base import Tool, label, register
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

# 冻结历史表：按 user_id + target_id IN (...) + target_type=1(卡) 隔离，
# operation_type=1 取冻结记录。一次查回所有冻结卡的最新一条，避免 N+1。
# aiomysql 对 IN %s 接 tuple：传 ((c1, c2, c3),) 展开为 IN (c1,c2,c3)。
FREEZE_SQL = """
SELECT target_id, freeze_reason, reason_desc, create_time, auto_unfreeze_time
FROM t_tevaupay_bank_card_freeze_history
WHERE user_id=%s AND target_id IN %s AND target_type=1 AND operation_type=1 AND del=0
ORDER BY target_id, create_time DESC
"""

# card_status 字典（真实库列注释 + 后端 CardStatusEnum 双重核对；13/14 列注释缺失，按后端枚举补全）
_CARD_STATUS: dict[Any, str] = {
    100: "待申请",
    0: "开卡成功",
    1: "注销成功",
    2: "已锁定-仅限客户操作",
    3: "申请中",
    4: "开卡失败",
    5: "注销中",
    6: "注销失败",
    7: "已冻结-仅限管理员操作",
    8: "制作中",
    9: "卡片冻结",
    10: "卡片已过期",
    11: "取消开卡",
    12: "已发货",
    13: "添加中",
    14: "待激活",
}
# 币种：库列注释 1数字货币泰达币/2法币美元/3数字货币以太币；后端 CurrencyEnum 显示名以英文 code 为准，
# 3 在后端枚举为 ARB_ETH（非裸 ETH），按后端枚举对齐。
_CURRENCY: dict[Any, str] = {
    0: "UNKNOWN",
    1: "USDT",
    2: "USD",
    3: "ARB_ETH",
    4: "BNB",
    5: "TRX",
    6: "EUR",
    7: "BTCW",
    8: "HKD",
    9: "CNY",
    12: "IDR",
    15: "XUSD",
}
_CARD_TYPE: dict[Any, str] = {1: "实体卡", 2: "虚拟卡"}
# 冻结原因编码（真实库 freeze_reason 列注释 + 后端 FreezeReasonEnum）
_FREEZE_REASON: dict[Any, str] = {
    1: "黑名单商户交易",
    2: "超额消费导致负数",
    3: "不活跃扣费不足",
    4: "人工冻结卡",
    11: "黑名单到期自动解冻",
    12: "充值补足后自动解冻",
    13: "充值后扣费成功自动解冻",
    14: "人工解冻卡",
    21: "风控系统冻结账户",
    22: "人工冻结账户",
    23: "人工解冻账户",
}

# 处于冻结/锁定态、需要带出冻结原因的卡状态：9 卡片冻结、7 已冻结(管理员)、2 已锁定
_FROZEN_STATUSES = {2, 7, 9}


def _card_view(row: dict[str, Any], unmask: bool) -> dict[str, Any]:
    cn = row.get("card_number")
    status = row.get("card_status")
    return {
        "card_id": row["id"],
        "card_no": cn if unmask else mask_card_no(cn),
        "status_code": status,
        "status": label(_CARD_STATUS, status),
        "status_desc": row.get("card_status_description"),
        "balance": str(row["card_balance"]) if row.get("card_balance") is not None else None,
        "currency": label(_CURRENCY, row.get("card_currency")),
        "card_type": label(_CARD_TYPE, row.get("card_type")),
        "expiry_date": row.get("expiry_date"),
        "reject_reason": row.get("reject_reason"),
        "cancel_card_reason": row.get("cancel_card_reason"),
        "alias": row.get("card_alias_name"),
        "create_time": str(row["create_time"]) if row.get("create_time") else None,
    }


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户名下所有卡的状态（锁定/冻结看 status；冻结卡带出真实冻结原因；卡号脱敏，unmask 仅 engineer 代查）。

    N+1 消除：所有冻结/锁定卡的 freeze_history 一次 IN 批查，按 target_id 分组取最新。
    """
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=20)
    # 一次性收集需要查冻结历史的卡 id
    frozen_ids = [r["id"] for r in rows if r.get("card_status") in _FROZEN_STATUSES]
    freeze_by_card: dict[Any, dict[str, Any]] = {}
    if frozen_ids:
        freezes = await db.fetch_all(
            FREEZE_SQL,
            (user_id, tuple(frozen_ids)),
            limit=len(frozen_ids) * 4,
        )
        # ORDER BY target_id, create_time DESC → 同 target_id 第一条即最新
        for fr in freezes:
            tid = fr.get("target_id")
            if tid not in freeze_by_card:
                freeze_by_card[tid] = fr

    cards = []
    for r in rows:
        view = _card_view(r, unmask)
        if r.get("card_status") in _FROZEN_STATUSES:
            fr = freeze_by_card.get(r["id"])
            if fr:
                view["freeze_reason"] = label(_FREEZE_REASON, fr.get("freeze_reason"))
                view["freeze_reason_code"] = fr.get("freeze_reason")
                view["freeze_reason_desc"] = fr.get("reason_desc")
                view["freeze_time"] = str(fr["create_time"]) if fr.get("create_time") else None
                view["expected_unfreeze_time"] = (
                    str(fr["auto_unfreeze_time"]) if fr.get("auto_unfreeze_time") else None
                )
        cards.append(view)
    return {"cards": cards, "count": len(cards), "unmasked": unmask}


register(
    Tool(
        name="query_card",
        description=(
            "查询当前用户名下所有银行卡的状态与信息（卡号脱敏）。"
            "用户问'我的卡为什么被锁/冻结''卡状态''卡余额'时用。"
            "锁定/冻结看 status；冻结卡的真实冻结原因看 freeze_reason/freeze_reason_desc，"
            "预计解冻时间看 expected_unfreeze_time。"
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
