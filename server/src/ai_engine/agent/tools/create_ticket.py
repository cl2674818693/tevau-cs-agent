import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from typing import Any

import httpx

from ai_engine.agent.tools.base import Tool, register
from ai_engine.config import settings
from ai_engine.integrations.lark_webhook import send as _notify_lark
from ai_engine.observability import metrics
from ai_engine.persistence.tickets import append_ticket_event as _append_event
from ai_engine.persistence.tickets import create_ticket as _save_local
from ai_engine.persistence.tickets import find_open_ticket_for_subject as _find_open

VALID_CATEGORIES = {"bug", "事务", "CQ", "无信息", "人工介入"}
VALID_SEVERITIES = {"p0", "p1", "p2", "p3"}


def _new_external_id() -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"AI-{ts}-{secrets.token_hex(3)}"


def _sign(body: bytes) -> str:
    return hmac.new(settings.event_center_secret_current.encode(), body, hashlib.sha256).hexdigest()


async def _post(url: str, json: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
    async with httpx.AsyncClient(timeout=5.0) as client:
        return await client.post(url, json=json, headers=headers)


async def run(
    subject_id: str,
    user_type: str,
    conversation_id: int,
    category: str,
    summary: str,
    severity: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")
    if user_type not in ("c", "b"):
        raise ValueError("user_type must be 'c' or 'b'")

    # spec §11 工单风暴对策：同 subject 24h 内已有未关闭工单 → 追加证据，不新建。
    existing = await _find_open(subject_id, user_type)
    if existing:
        await _append_event(
            existing,
            event="evidence_added",
            actor="ai",
            comment=summary,
            raw={"category": category, "severity": severity, "evidence": evidence},
        )
        return {"external_ticket_id": existing, "appended_to_existing": True}

    ext_id = _new_external_id()
    # spec §7.1：C 端工单填 user_id，B 端填 bu_id。身份由 tool_router 注入（subject_id）。
    subject_key = "user_id" if user_type == "c" else "bu_id"
    payload: dict[str, object] = {
        "source": "ai_engine",
        "external_ticket_id": ext_id,
        "user_type": user_type,
        subject_key: subject_id,
        "category": category,
        "summary": summary,
        "severity": severity,
        "evidence": evidence,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # 1. 本地落库（兜底，确保引擎自有记录）
    await _save_local(external_id=ext_id, conversation_id=conversation_id, payload=payload)
    metrics.tickets_created.labels(category=category, severity=severity, user_type=user_type).inc()

    # 2. 推事项中心（带 HMAC 签名）
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-Signature": _sign(body_bytes), "Content-Type": "application/json"}
    pushed = False
    try:
        resp = await _post(settings.event_center_url, json=payload, headers=headers)
        pushed = 200 <= getattr(resp, "status_code", 500) < 300
    except Exception:
        pushed = False

    # 3. 如失败，触发 Lark 兜底
    if not pushed:
        text = f"[兜底] 工单 {ext_id} 推事项中心失败：{category} / {severity} / {summary[:80]}"
        await _notify_lark({"text": text})

    # 4. 人工介入类工单：同步切 mode=human_pending，与 /request-human 端点行为对齐。
    #    否则会话仍是 mode='ai'，admin "会话" 列表筛 mode!=ai 看不到这个待接管会话。
    #    已经在 human_takeover/human_pending 的不重切（避免 mode_change 抖动 + 重复 SSE）。
    if category == "人工介入" and conversation_id:
        await _ensure_human_pending(conversation_id)

    return {"external_ticket_id": ext_id, "pushed_to_event_center": pushed}


async def _ensure_human_pending(conversation_id: int) -> None:
    """当前 mode=ai 时切到 human_pending 并广播 mode_change。失败不阻断工单创建。
    import 内置在函数体内避免与 staff_conversations._publish 形成循环依赖。"""
    try:
        from ai_engine.api.staff_conversations import publish_conversation_event
        from ai_engine.persistence import conversations as conv_dao
        from ai_engine.persistence.staff_metrics import refresh_human_pending

        mode, _ = await conv_dao.get_mode(conversation_id)
        if mode != "ai":
            return
        await conv_dao.set_mode(conversation_id, "human_pending")
        await refresh_human_pending()
        publish_conversation_event(
            conversation_id, {"type": "mode_change", "to": "human_pending"}
        )
    except Exception:
        # 切 mode 失败不阻断工单创建——工单已经入库，事项中心已推送
        pass


register(
    Tool(
        name="create_ticket",
        description=(
            "当 AI 无法当场解决时，创建工单并推送到事项中心。"
            "category ∈ {bug,事务,CQ,无信息,人工介入}，severity ∈ {p0..p3}。"
            "**不指定分派人**（分派由事项中心按规则决定，见 spec §7.3）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": sorted(VALID_CATEGORIES)},
                "summary": {"type": "string", "minLength": 5, "maxLength": 500},
                "severity": {"type": "string", "enum": sorted(VALID_SEVERITIES)},
                "evidence": {"type": "object"},
            },
            "required": ["category", "summary", "severity", "evidence"],
        },
        handler=run,
        requires_subject_id=True,
        subject_field="subject_id",
    )
)
