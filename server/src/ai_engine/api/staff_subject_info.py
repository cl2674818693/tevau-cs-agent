"""客服侧：会话主体 (C 端用户 / B 端公司) 业务信息聚合。

admin 详情页 InfoCard 调一次拿全：用户基本信息 + 近 30 天交易聚合 + 客户端环境。
不复用 agent.tools.query_user 直接返回脱敏字段——admin 是内部员工，给明文（与 spec §13.3 一致）。
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import client_info as ci_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.business_db import get_db

router = APIRouter()


# C 端用户主表字段（query_user 同源）
_C_USER_SQL = """
SELECT id, user_code, email_address, mobile_phone, nick_name, user_status, kyc_status,
       open_card_status, registration_time, last_login_time
FROM t_tevaupay_user
WHERE id=%s AND del=0
"""

# C 端最近 30 天交易聚合：按币种分组（混币种相加无意义）
_C_TX_AGG_SQL = """
SELECT currency, COUNT(*) AS cnt, COALESCE(SUM(trade_amount), 0) AS amt
FROM t_tevaupay_card_recharge_records
WHERE user_id=%s AND status IN (3, 4, 8) AND type NOT IN (25, 22)
  AND date_time_stamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY currency
ORDER BY cnt DESC
LIMIT 5
"""

_USER_STATUS = {0: "正常", 1: "冻结", 2: "注销"}
_KYC_STATUS = {0: "未认证", 1: "已认证", 2: "认证失败", 3: "审核中"}
_OPEN_CARD = {0: "未开卡", 1: "已开卡"}
_CURRENCY = {
    1: "USDT", 2: "USD", 3: "ARB_ETH", 4: "BNB", 5: "TRX", 6: "EUR",
    7: "BTCW", 8: "HKD", 9: "CNY", 12: "IDR", 15: "XUSD",
}
# B 端 t_nexus_company_info.status: 0=待开启 1=运行中 2=已停用
_BU_STATUS = {0: "待开启", 1: "运行中", 2: "已停用"}


def _label(table: dict[Any, str], v: Any) -> str | None:
    return table.get(v) if v is not None else None


async def _c_subject_info(user_id: str) -> dict[str, Any]:
    db = get_db("unlimitpay")
    row = await db.fetch_one(_C_USER_SQL, (user_id,))
    if not row:
        return {"found": False}
    txs_rows = await db.fetch_all(_C_TX_AGG_SQL, (row["id"],), limit=5)
    txs = [
        {
            "currency": _label(_CURRENCY, r.get("currency")) or str(r.get("currency")),
            "count": int(r.get("cnt") or 0),
            "amount": str(r.get("amt")) if r.get("amt") is not None else "0",
        }
        for r in txs_rows
    ]
    reg = row.get("registration_time")
    last = row.get("last_login_time")
    return {
        "found": True,
        "user_id": row["id"],
        "user_code": row.get("user_code"),
        "nick_name": row.get("nick_name"),
        "email": row.get("email_address"),  # admin 内部，给明文
        "phone": row.get("mobile_phone"),
        "user_status": _label(_USER_STATUS, row.get("user_status")),
        "kyc_status": _label(_KYC_STATUS, row.get("kyc_status")),
        "open_card_status": _label(_OPEN_CARD, row.get("open_card_status")),
        "registration_time": str(reg) if reg else None,
        "last_login_time": str(last) if last else None,
        "recent_30d_transactions": txs,
    }


async def _b_subject_info(tenant_id: str) -> dict[str, Any]:
    """B 端 subject_id 是 tenant_id，只能从 t_nexus_company_info 取公司维度信息。
    具体到某终端用户需 user_code，B 端会话不持有，所以不查 t_nexus_user。"""
    db = get_db("nexus")
    row = await db.fetch_one(
        "SELECT tenant_id, company_name, status FROM t_nexus_company_info "
        "WHERE tenant_id=%s AND del_flag=0",
        (tenant_id,),
    )
    if not row:
        return {"found": False}
    return {
        "found": True,
        "tenant_id": row.get("tenant_id"),
        "company_name": row.get("company_name"),
        "status": _label(_BU_STATUS, row.get("status")),
    }


@router.get("/staff/api/v1/conversations/{conv_id}/subject-info")
async def subject_info(
    conv_id: int, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """会话主体业务信息 + 客户端环境（一次性聚合，admin 详情页 InfoCard 用）。
    业务库未配置（开发/测试场景 unlimitpay_db_url=None）时仅返回 client_info。"""
    conv = await conv_dao.get_conversation_meta(conv_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")

    user_type = str(conv["user_type"])
    subject_id = str(conv["subject_id"])
    subject: dict[str, Any] = {"user_type": user_type, "subject_id": subject_id, "found": False}
    try:
        if user_type == "c":
            subject = {"user_type": "c", "subject_id": subject_id, **await _c_subject_info(subject_id)}
        elif user_type == "b":
            subject = {"user_type": "b", "subject_id": subject_id, **await _b_subject_info(subject_id)}
    except Exception:
        # 业务库未连/SQL 失败时不阻断接口：client_info 仍能返回，subject.found=False 即可
        subject["found"] = False

    return {
        "subject": subject,
        "client_info": await ci_dao.get_client_info(conv_id),
    }
