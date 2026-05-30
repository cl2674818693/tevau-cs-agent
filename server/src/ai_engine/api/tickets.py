import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from ai_engine.api.staff_conversations import _publish
from ai_engine.auth.staff_session import require_staff
from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence.tickets import (
    append_ticket_event,
    get_ticket,
    list_tickets,
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
        _publish(
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


@router.get("/staff/api/v1/tickets")
async def staff_list_tickets(
    open: bool = Query(default=False),
    severity: str | None = Query(default=None),
    category: str | None = Query(default=None),
    before_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    """运营只读工单列表（看 + 跳会话）。外部事项中心是状态真源，本地仅只读镜像。

    可选筛选：open（只看未关闭）/ severity / category；游标分页：before_id。
    """
    return {
        "tickets": await list_tickets(
            open_only=open,
            severity=severity,
            category=category,
            limit=limit,
            before_id=before_id,
        )
    }


@router.get("/staff/api/v1/tickets/{external_id}")
async def staff_get_ticket(
    external_id: str, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """工单详情（含事件链）。本地只读镜像，外部事项中心为状态真源。"""
    t = await get_ticket(external_id)
    if t is None:
        raise HTTPException(404, "ticket not found")
    return t


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
