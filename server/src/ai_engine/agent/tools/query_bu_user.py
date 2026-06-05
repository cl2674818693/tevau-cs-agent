from typing import Any

from ai_engine.agent.tools.base import Tool, gated, register
from ai_engine.integrations.redact import mask_email, mask_id_card, mask_phone
from ai_engine.persistence.business_db import get_db

# B 端对接后，其终端用户的实名(KYC)是在我方平台过的，数据落 tevau_nexus_test，按 tenant_id 隔离。
# 关联链：user_code →(t_nexus_user.id)→ t_nexus_user_kyc.user_id（存 id 的字符串）。
_USER_SQL = """
SELECT id, user_status, open_card_status, audit_status, kyc_time, registration_time,
       create_time, email_address, phone_code, phone_number
FROM t_nexus_user
WHERE tenant_id=%s AND user_code=%s AND del_flag=0
LIMIT 1
"""
_KYC_SQL = """
SELECT audit_status, identity_failer_reason, certification_status, country_area, live_country,
       identity_card_type, first_name, last_name, first_name_en, last_name_en, identity_card,
       birthday, phone_code, phone_number, address, city, post_code, request_time, audit_pass_time
FROM t_nexus_user_kyc
WHERE tenant_id=%s AND user_id=%s AND del_flag=0
ORDER BY id DESC
LIMIT 1
"""
# 最近一次审核记录的第三方失败原因（"KYC 卡住/反复失败"排查关键）
_AUDIT_SQL = """
SELECT audit_status, third_party_audit_result, third_party_fail_reason, identity_failer_reason,
       person_audit_status, create_time
FROM t_nexus_user_kyc_audit_record
WHERE tenant_id=%s AND user_id=%s AND del_flag=0
ORDER BY id DESC
LIMIT 1
"""

_USER_STATUS: dict[Any, str] = {0: "正常", 1: "冻结", 2: "注销"}
_OPEN_CARD: dict[Any, str] = {0: "未开卡", 1: "已开卡"}
_USER_KYC: dict[Any, str] = {0: "未认证", 1: "已认证", 2: "认证失败", 3: "审核中"}
_KYC_AUDIT: dict[Any, str] = {0: "审核中", 1: "认证通过", 2: "未通过", 3: "已作废"}
_ID_TYPE: dict[Any, str] = {1: "身份证", 2: "护照"}


async def run(tenant_id: str, user_code: str, unmask: bool = False) -> dict[str, Any]:
    """按 user_code 查 BU 旗下终端用户的状态 + KYC（审核状态/失败原因）。KYC 卡住/失败排查用。"""
    if not tenant_id:
        return {"user": None, "note": "缺少 tenant 身份"}
    if not user_code:
        return {"user": None, "note": "需提供 user_code"}
    db = get_db("nexus")
    u = await db.fetch_one(_USER_SQL, (tenant_id, user_code))
    if not u:
        return {"user": None, "note": f"该 BU 下无 user_code={user_code} 的用户"}

    user: dict[str, Any] = {
        "user_code": user_code,
        "user_status": _USER_STATUS.get(u.get("user_status"), u.get("user_status")),
        "open_card_status": _OPEN_CARD.get(u.get("open_card_status"), u.get("open_card_status")),
        "kyc_status": _USER_KYC.get(u.get("audit_status"), f"未知({u.get('audit_status')})"),
        "kyc_time": str(u["kyc_time"]) if u.get("kyc_time") else None,
        "registration_time": str(u["registration_time"]) if u.get("registration_time") else None,
        "email": mask_email(u.get("email_address")),
        "phone": mask_phone(u.get("phone_number")),
    }

    kyc_id = str(u.get("id"))
    k = await db.fetch_one(_KYC_SQL, (tenant_id, kyc_id))
    if k:
        kyc: dict[str, Any] = {
            "audit_status": _KYC_AUDIT.get(k.get("audit_status"), k.get("audit_status")),
            # KYC 厂商失败明细（算法置信度/触发规则），默认 gate；engineer 代查可解锁
            "failed_reason": gated(k.get("identity_failer_reason"), unmask),
            "country": k.get("live_country") or k.get("country_area"),
            "id_type": _ID_TYPE.get(k.get("identity_card_type")),
            "request_time": str(k["request_time"]) if k.get("request_time") else None,
            "audit_pass_time": str(k["audit_pass_time"]) if k.get("audit_pass_time") else None,
        }
        if unmask:  # engineer 代查：高敏 PII
            name = (
                " ".join(x for x in (k.get("first_name_en"), k.get("last_name_en")) if x)
                or f"{k.get('last_name') or ''}{k.get('first_name') or ''}".strip()
            )
            kyc["full_name"] = name or None
            kyc["identity_card"] = k.get("identity_card")
            kyc["birthday"] = str(k["birthday"]) if k.get("birthday") else None
            kyc["address"] = (
                ", ".join(x for x in (k.get("address"), k.get("city"), k.get("post_code")) if x)
                or None
            )
        else:
            kyc["identity_card"] = mask_id_card(k.get("identity_card"))
            kyc["pii_note"] = "姓名/证件/地址已隐藏（engineer 代查可解锁）"
        user["kyc"] = kyc

    # 审核失败/卡住时，带上最近一次审核记录的第三方原因（比 KYC 主表的 failed_reason 更具体）
    a = await db.fetch_one(_AUDIT_SQL, (tenant_id, kyc_id))
    if a and (a.get("third_party_fail_reason") or a.get("identity_failer_reason")):
        user["latest_audit"] = {
            "audit_status": _KYC_AUDIT.get(a.get("audit_status"), a.get("audit_status")),
            # 第三方厂商返回的失败原文：含厂商错误码/算法触发规则，默认 gate
            "third_party_reason": gated(a.get("third_party_fail_reason"), unmask),
            "failed_reason": gated(a.get("identity_failer_reason"), unmask),
            "manual_audit": a.get("person_audit_status") == 1,
            "time": str(a["create_time"]) if a.get("create_time") else None,
        }
    return {"user": user, "unmasked": unmask}


register(
    Tool(
        name="query_bu_user",
        description=(
            "按 user_code 查询当前 BU 旗下终端用户的状态与实名(KYC)情况。"
            "能看到：用户状态(正常/冻结)、是否开卡、KYC 审核状态、失败原因、"
            "最近一次审核的第三方原因。"
            "数据来自 t_nexus_user + t_nexus_user_kyc。"
            "BU 问'某用户 KYC 为什么没过''审核到哪了''卡在 submitted''用户被冻结'时用。"
            "姓名/证件/地址脱敏。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入当前 BU 身份
                "user_code": {"type": "string", "description": "终端用户编号，如 CB13748899"},
            },
            "required": ["user_code"],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
