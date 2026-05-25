from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_card_no, mask_email, mask_phone
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_bank_card_company（B 端客户银行卡主表），按 tenant_id 隔离。
# 可选 card_id 过滤：定位 BU 旗下某张具体卡（如 CIDV.../CIDP... 开头的卡 id）。
_BASE_SQL = """
SELECT card_id, card_number, card_status, card_status_desc, card_type, card_channel_type,
       card_currency, card_title, three_card_id, account_num,
       user_id, user_code, email, phone_number, dial_code,
       active_time, create_time, remark
FROM t_nexus_bank_card_company
WHERE tenant_id=%s AND del_flag=0
"""

_STATUS: dict[Any, str] = {
    1: "申请中",
    2: "制作中",
    3: "已发货",
    4: "已激活",
    5: "注销中",
    6: "已注销",
    7: "已冻结",
    8: "管理员操作冻结",
    9: "已过期",
    10: "等待绑定(代理商)",
    11: "绑定中(代理商)",
}
_CARD_TYPE: dict[Any, str] = {1: "实体卡", 2: "虚拟卡"}
_CHANNEL: dict[Any, str] = {1: "Reap", 2: "SX"}
_CURRENCY: dict[Any, str] = {1: "USD"}


async def run(
    tenant_id: str,
    card_id: str | None = None,
    card_number: str | None = None,
    unmask: bool = False,
) -> dict[str, Any]:
    """查当前 BU 旗下银行卡信息与状态（按 card_id 或卡号 PAN 定位某张卡）。卡号/邮箱/手机脱敏。"""
    if not tenant_id:
        return {"cards": [], "count": 0, "note": "缺少 tenant 身份"}
    sql = _BASE_SQL
    params: list[Any] = [tenant_id]
    if card_id:
        sql += " AND card_id=%s"
        params.append(card_id)
    if card_number:  # 工单常给完整卡号(PAN)而非 card_id；按数字精确匹配
        digits = "".join(ch for ch in card_number if ch.isdigit())
        sql += " AND card_number=%s"
        params.append(digits)
    sql += " ORDER BY create_time DESC"
    db = get_db("nexus")
    rows = await db.fetch_all(sql, tuple(params), limit=20)
    cards = []
    for r in rows:
        item = {
            "card_id": r.get("card_id"),
            "card_no": r.get("card_number") if unmask else mask_card_no(r.get("card_number")),
            "status_code": r.get("card_status"),
            "status": _STATUS.get(r.get("card_status"), f"未知({r.get('card_status')})"),
            "status_desc": r.get("card_status_desc"),
            "card_type": _CARD_TYPE.get(r.get("card_type")),
            "channel": _CHANNEL.get(r.get("card_channel_type"), r.get("card_channel_type")),
            "currency": _CURRENCY.get(r.get("card_currency"), r.get("card_currency")),
            "title": r.get("card_title"),
            "user_code": r.get("user_code"),
            "email": mask_email(r.get("email")),
            "phone": mask_phone(r.get("phone_number")),
            "active_time": str(r["active_time"]) if r.get("active_time") else None,
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
            "remark": r.get("remark"),
        }
        if unmask:  # engineer 代查：三方卡 id / 现金账户号
            item["three_card_id"] = r.get("three_card_id")
            item["account_num"] = r.get("account_num")
        cards.append(item)
    return {"cards": cards, "count": len(cards), "unmasked": unmask}


register(
    Tool(
        name="query_bu_card",
        description=(
            "查询当前 BU(企业租户)旗下银行卡的信息与状态（卡号/邮箱/手机脱敏）。"
            "可传 card_id（CIDV/CIDP 开头）或 card_number（完整卡号 PAN，如 4938...）定位某张卡。"
            "BU 问'某张卡状态''这张卡是不是我们发的''卡为什么冻结'时用，也是排查卡交易的第一步。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入当前 BU 身份
                "card_id": {"type": "string", "description": "可选，按卡 id 定位（CIDV/CIDP…）"},
                "card_number": {"type": "string", "description": "可选，按完整卡号 PAN 定位"},
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
