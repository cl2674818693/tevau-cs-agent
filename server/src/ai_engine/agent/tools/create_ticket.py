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
from ai_engine.persistence.tickets import create_ticket as _save_local

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
    bu_id: str,
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

    ext_id = _new_external_id()
    payload: dict[str, object] = {
        "source": "ai_engine",
        "external_ticket_id": ext_id,
        "user_type": "b",
        "bu_id": bu_id,
        "category": category,
        "summary": summary,
        "severity": severity,
        "evidence": evidence,
        "created_at": datetime.now(UTC).isoformat(),
    }

    # 1. 本地落库（兜底，确保引擎自有记录）
    await _save_local(external_id=ext_id, conversation_id=conversation_id, payload=payload)

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

    return {"external_ticket_id": ext_id, "pushed_to_event_center": pushed}


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
                "bu_id": {"type": "string"},
                "category": {"type": "string", "enum": sorted(VALID_CATEGORIES)},
                "summary": {"type": "string", "minLength": 5, "maxLength": 500},
                "severity": {"type": "string", "enum": sorted(VALID_SEVERITIES)},
                "evidence": {"type": "object"},
            },
            "required": ["category", "summary", "severity", "evidence"],
        },
        handler=run,
        requires_subject_id=True,
    )
)
