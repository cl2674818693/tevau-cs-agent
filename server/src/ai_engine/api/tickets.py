import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request

from ai_engine.api.staff_conversations import publish_conversation_event
from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence.tickets import (
    append_ticket_event,
    get_ticket,
    update_ticket_severity,
)

router = APIRouter()


def _verify(raw: bytes, sig: str) -> bool:
    # spec §7.4 双 key 热轮换：current / previous 任一通过即可
    for key in (settings.event_center_secret_current, settings.event_center_secret_previous):
        if not key:
            continue
        expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, sig):
            return True
    return False


@router.post("/api/v1/tickets/{external_id}/events")
async def receive_event(
    external_id: str, request: Request, x_signature: str = Header(default="")
) -> dict[str, bool]:
    raw = await request.body()
    if not _verify(raw, x_signature):
        raise HTTPException(401, "bad signature")
    body = json.loads(raw)
    event = body.get("event", "")
    await append_ticket_event(
        external_id=external_id,
        event=event,
        actor=body.get("actor"),
        comment=body.get("comment"),
        raw=body,
    )
    # spec §7.2 修订：event=in_progress 时可带 severity（受理人在事项中心覆盖）
    if event == "in_progress" and body.get("severity"):
        await update_ticket_severity(external_id=external_id, severity=body["severity"])
    # spec §7.2 + Task 9：推给该会话的 ticket-events-stream（SSE 替换轮询）
    ticket = await get_ticket(external_id)
    if ticket is not None:
        publish_conversation_event(
            int(ticket["conversation_id"]),  # type: ignore[call-overload]
            {
                "type": event,
                "external_id": external_id,
                "actor": body.get("actor"),
                "comment": body.get("comment"),
            },
        )
        if event in ("resolved", "closed"):
            _observe_resolution(ticket)
    return {"ok": True}


def _observe_resolution(ticket: dict[str, object]) -> None:
    """工单解决耗时入 histogram（spec §11）。created_at 为 sqlite 朴素 UTC。"""
    try:
        created = datetime.fromisoformat(str(ticket["created_at"]))
    except (ValueError, KeyError):
        return
    elapsed = (datetime.now(UTC).replace(tzinfo=None) - created).total_seconds()
    payload = json.loads(str(ticket.get("payload_json", "{}")))
    category = str(payload.get("category", "unknown"))
    if elapsed >= 0:
        metrics.ticket_resolution_seconds.labels(category=category).observe(elapsed)
