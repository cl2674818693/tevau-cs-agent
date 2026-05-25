from typing import Any

from ai_engine.agent.tools.base import Tool, register
from ai_engine.persistence.business_db import get_db

# 真实库 tevau_nexus_test.t_nexus_jit_request_log（JIT 外部授权请求日志），按 tenant_id 隔离。
# 发卡方对每笔卡消费的实时 approve/decline 决策 —— 排查"某笔消费为什么被拒/为什么放行"的根因表。
_BASE_SQL = """
SELECT transaction_id, card_id, decision, decline_reason, trans_amount, trans_currency,
       card_fee, channel_fee, http_status, duration_ms, error_message,
       channel_type, request_time, response_time, request_body, response_body
FROM t_nexus_jit_request_log
WHERE tenant_id=%s
"""

_CHANNEL: dict[Any, str] = {1: "Reap", 2: "SX"}


def _clip(v: Any, n: int = 800) -> str | None:
    if v is None:
        return None
    s = v if isinstance(v, str) else str(v)
    return s[:n] + ("…" if len(s) > n else "")


async def run(tenant_id: str, card_id: str | None = None, unmask: bool = False) -> dict[str, Any]:
    """查某张卡每笔消费的 JIT 授权决策（APPROVED/DECLINED/TIMEOUT 及拒绝原因）。消费被拒排查用。"""
    if not tenant_id:
        return {"decisions": [], "count": 0, "note": "缺少 tenant 身份"}
    sql = _BASE_SQL
    params: tuple[Any, ...] = (tenant_id,)
    if card_id:
        sql += " AND card_id=%s"
        params = (tenant_id, card_id)
    sql += " ORDER BY request_time DESC"
    db = get_db("nexus")
    rows = await db.fetch_all(sql, params, limit=20)
    decisions = []
    for r in rows:
        item: dict[str, Any] = {
            "transaction_id": r.get("transaction_id"),
            "card_id": r.get("card_id"),
            "decision": r.get("decision"),  # APPROVED / DECLINED / TIMEOUT
            "decline_reason": r.get("decline_reason"),
            "amount": str(r["trans_amount"]) if r.get("trans_amount") is not None else None,
            "currency": r.get("trans_currency"),
            "card_fee": str(r["card_fee"]) if r.get("card_fee") is not None else None,
            "channel_fee": str(r["channel_fee"]) if r.get("channel_fee") is not None else None,
            "http_status": r.get("http_status"),
            "duration_ms": r.get("duration_ms"),
            "error_message": r.get("error_message"),
            "channel": _CHANNEL.get(r.get("channel_type"), r.get("channel_type")),
            "request_time": str(r["request_time"]) if r.get("request_time") else None,
            "response_time": str(r["response_time"]) if r.get("response_time") else None,
        }
        if unmask:  # engineer 代查：完整授权请求/响应报文
            item["request_body"] = _clip(r.get("request_body"))
            item["response_body"] = _clip(r.get("response_body"))
        decisions.append(item)
    return {"decisions": decisions, "count": len(decisions), "unmasked": unmask}


register(
    Tool(
        name="query_card_jit_decision",
        description=(
            "查询某张卡每笔消费的 JIT 实时授权决策（t_nexus_jit_request_log）。"
            "能看到：授权结果 APPROVED/DECLINED/TIMEOUT、拒绝原因、交易金额、耗时。"
            "BU 问'这笔消费为什么被拒''为什么扣款失败''授权是否正常'时用。"
            "可配合 query_card_authorization 一起看。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tenant_id": {"type": "string"},  # router 强制注入
                "card_id": {"type": "string", "description": "按卡 id 过滤该卡的授权决策"},
            },
            "required": [],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="tenant_id",
        supports_unmask=True,
    )
)
