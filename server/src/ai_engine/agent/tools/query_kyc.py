from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.integrations.redact import mask_id_card, mask_phone
from ai_engine.persistence.business_db import get_db

# 真实库 unlimitpay_test.t_tevaupay_user_kyc（实名信息），按 user_id 隔离
SQL = """
SELECT audit_status, identity_failer_reason, certification_status, country_area, live_country,
       identity_card_type, first_name, last_name, identity_card, birthday,
       phone_code, phone_number, address, city, post_code, request_time, audit_pass_time
FROM t_tevaupay_user_kyc
WHERE user_id=%s AND del=0
ORDER BY id DESC
"""

_AUDIT: dict[Any, str] = {0: "审核中", 1: "认证通过", 2: "未通过"}
_ID_TYPE: dict[Any, str] = {1: "身份证", 2: "护照"}


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户实名(KYC)状态与失败原因。姓名/证件号/地址等高敏字段脱敏，engineer 可解锁。"""
    db = get_db("unlimitpay")
    row = await db.fetch_one(SQL, (user_id,))
    if not row:
        return {"kyc": None, "note": f"user {user_id} 无 KYC 记录"}
    out: dict[str, Any] = {
        "audit_status": _AUDIT.get(row.get("audit_status"), row.get("audit_status")),
        "failed_reason": row.get("identity_failer_reason"),
        "certification_status": row.get("certification_status"),
        "country": row.get("live_country") or row.get("country_area"),
        "id_type": _ID_TYPE.get(row.get("identity_card_type")),
        "request_time": str(row["request_time"]) if row.get("request_time") else None,
        "audit_pass_time": str(row["audit_pass_time"]) if row.get("audit_pass_time") else None,
    }
    if unmask:  # engineer 代查解锁高敏 PII（spec §13.3）
        out["full_name"] = (
            f"{row.get('last_name') or ''}{row.get('first_name') or ''}".strip() or None
        )
        out["identity_card"] = row.get("identity_card")
        out["birthday"] = str(row["birthday"]) if row.get("birthday") else None
        out["phone"] = f"{row.get('phone_code') or ''}{row.get('phone_number') or ''}" or None
        out["address"] = (
            ", ".join(x for x in (row.get("address"), row.get("city"), row.get("post_code")) if x)
            or None
        )
    else:
        out["identity_card"] = mask_id_card(row.get("identity_card"))
        out["phone"] = mask_phone(row.get("phone_number"))
        out["pii_note"] = "姓名/证件/地址已隐藏（engineer 代查可解锁）"
    return {"kyc": out, "unmasked": unmask}


register(
    Tool(
        name="query_kyc",
        description=(
            "查询当前用户的实名认证(KYC)状态与失败原因。用户问'实名审核到哪了''为什么没通过'时用。"
            "姓名/证件号/地址等高敏信息默认隐藏。"
        ),
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
