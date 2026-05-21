from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_third_request_log（下游请求日志），按 tenant_id 隔离
# 注意：tenant_id 存在 NULL 脏数据；WHERE tenant_id=%s 用具体值，NULL 行不会匹配（安全）
SQL = """
SELECT order_sn, channel_type, third_url, elapsed_time, create_time,
       tenant_req_bod, tenant_resp_bod, third_req_bod, third_resp_bod
FROM t_nexus_third_request_log
WHERE tenant_id=%s
ORDER BY create_time DESC
"""

_CHANNEL: dict[Any, str] = {1: "rampable"}


def _clip(v: Any, n: int = 800) -> str | None:
    if v is None:
        return None
    s = v if isinstance(v, str) else str(v)
    return s[:n] + ("…" if len(s) > n else "")


async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU 调接口的下游请求日志（排查某次请求为何失败）。报文默认不返回，engineer 可解锁。"""
    if not tenant_id:
        return {"logs": [], "count": 0, "note": "缺少 tenant 身份"}
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)
    logs = []
    for r in rows:
        item: dict[str, Any] = {
            "order_sn": r.get("order_sn"),
            "channel": _CHANNEL.get(r.get("channel_type"), r.get("channel_type")),
            "third_url": r.get("third_url"),
            "elapsed_time": str(r["elapsed_time"]) if r.get("elapsed_time") is not None else None,
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
        }
        if unmask:  # 报文可能含卡号/金额/客户信息，仅 engineer 代查解锁
            item["tenant_req"] = _clip(r.get("tenant_req_bod"))
            item["tenant_resp"] = _clip(r.get("tenant_resp_bod"))
            item["third_req"] = _clip(r.get("third_req_bod"))
            item["third_resp"] = _clip(r.get("third_resp_bod"))
        logs.append(item)
    return {"logs": logs, "count": len(logs), "unmasked": unmask}


register(
    Tool(
        name="query_bu_request_log",
        description=(
            "查询当前 BU 调用接口的下游请求日志（排查'某次请求为什么失败'）。"
            "默认只看订单号/URL/耗时/时间；完整请求响应报文仅 engineer 代查可见。"
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
