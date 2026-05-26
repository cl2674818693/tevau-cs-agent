from typing import Any

from ai_engine.agent.tools.base import Tool, label, register
from ai_engine.integrations.redact import mask_email, mask_phone
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_user（C 端用户主表），按主键 id 隔离（= 当前登录 user_id）
SQL = """
SELECT id, user_code, email_address, mobile_phone, nick_name, user_status, kyc_status,
       open_card_status, registration_time, last_login_time
FROM t_tevaupay_user
WHERE id=%s AND del=0
"""

_USER_STATUS: dict[Any, str] = {0: "正常", 1: "冻结", 2: "注销"}
_KYC_STATUS: dict[Any, str] = {0: "未认证", 1: "已认证", 2: "认证失败", 3: "审核中"}
_OPEN_CARD: dict[Any, str] = {0: "未开卡", 1: "已开卡"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户的账户概览（状态/KYC 概览/开卡状态；邮箱手机脱敏）。"""
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (user_id,))
    if not row:
        return {"user": None, "note": f"user {user_id} not found"}
    email = row.get("email_address")
    phone = row.get("mobile_phone")
    reg = row.get("registration_time")
    last = row.get("last_login_time")
    return {
        "user": {
            "user_id": row["id"],
            "user_code": row.get("user_code"),
            "nick_name": row.get("nick_name"),
            "email": email if unmask else mask_email(email),
            "phone": phone if unmask else mask_phone(phone),
            "user_status": label(_USER_STATUS, row.get("user_status")),
            "kyc_status": label(_KYC_STATUS, row.get("kyc_status")),
            "open_card_status": label(_OPEN_CARD, row.get("open_card_status")),
            "registration_time": str(reg) if reg else None,
            "last_login_time": str(last) if last else None,
        },
        "unmasked": unmask,
    }


register(
    Tool(
        name="query_user",
        description=(
            "查询当前用户的账户概览（账户状态、KYC 状态、开卡状态；邮箱手机已脱敏）。"
            "用户问'我的账户状态''实名过了吗'时用。"
        ),
        input_schema={
            "type": "object",
            "properties": {"user_id": {"type": "string"}},  # router 强制注入
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="user_id",
        supports_unmask=True,
    )
)
