from typing import Any

from ai_engine.agent.tools.base import Tool, label, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_transaction_issuer_log（交易三方发卡方请求日志），按 tenant_id 隔离。
# 后端实体 TransactionIssuerLog.java（@TableName 同名），写入方 CardProviderHandlerLogServiceImpl。
# 隔离：tenant_id varchar(32)，存在 NULL 脏数据；WHERE tenant_id=%s 严格等值，NULL 行不匹配（安全）。
# response_body 为发卡方返回报文（失败时是 error 文本，成功是 result），可能含卡号/金额/客户信息，
# 默认不返回，engineer 代查解锁。
SQL = """
SELECT transaction_order_no, url, transaction_status, transaction_type,
       transaction_time, create_time, response_body
FROM t_nexus_transaction_issuer_log
WHERE tenant_id=%s
ORDER BY create_time DESC
"""

# transaction_status：以后端 LogEnum 为准（写入方用 LogEnum），与列注释/数据分布一致。
_STATUS: dict[Any, str] = {1: "成功", 2: "失败", 3: "请求中"}

# transaction_type：列注释枚举。
_TX_TYPE: dict[Any, str] = {
    1: "充值卡记录",
    2: "提现卡记录",
    3: "申请卡记录",
    4: "卡消费记录",
    5: "卡ATM提现记录",
    6: "卡销户记录",
}


def _clip(v: Any, n: int = 800) -> str | None:
    if v is None:
        return None
    s = v if isinstance(v, str) else str(v)
    return s[:n] + ("…" if len(s) > n else "")


async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU 调发卡方接口的三方请求日志（排查某笔交易请求为何失败）。

    默认看交易订单号/发卡方 URL/交易状态/类型/时间；发卡方完整响应报文 response_body
    默认不返回，engineer 代查可解锁。
    """
    if not tenant_id:
        return {"logs": [], "count": 0, "note": "缺少 tenant 身份"}
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)
    logs = []
    for r in rows:
        item: dict[str, Any] = {
            "transaction_order_no": r.get("transaction_order_no"),
            "url": r.get("url"),
            "transaction_status": label(_STATUS, r.get("transaction_status")),
            "transaction_type": label(_TX_TYPE, r.get("transaction_type")),
            "transaction_time": str(r["transaction_time"]) if r.get("transaction_time") else None,
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        if unmask:  # 发卡方响应报文可能含卡号/金额/客户信息，仅 engineer 代查解锁
            item["response_body"] = _clip(r.get("response_body"))
        logs.append(item)
    return {"logs": logs, "count": len(logs), "unmasked": unmask}


register(
    Tool(
        name="query_bu_request_log",
        description=(
            "查询当前 BU 调用发卡方接口的三方请求日志（排查'某笔交易请求为什么失败'）。"
            "默认只看交易订单号/发卡方 URL/交易状态/交易类型/时间；"
            "发卡方完整响应报文仅 engineer 代查可见。"
        ),
        input_schema={
            "type": "object",
            "properties": {"tenant_id": {"type": "string"}},
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
