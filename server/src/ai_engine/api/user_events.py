import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.agent.tools.create_ticket import run as create_ticket_run
from ai_engine.api.staff_conversations import _publish
from ai_engine.auth.bu_session import USER_TYPE_GUEST, resolve_identity
from ai_engine.integrations.event_center_client import push_event_center
from ai_engine.observability import metrics
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import routing_rules
from ai_engine.persistence import tickets as ticket_dao
from ai_engine.persistence.staff_metrics import refresh_human_pending

router = APIRouter()


class RequestHumanIn(BaseModel):
    reason: str | None = None


@router.post("/api/v1/conversations/{conv_id}/request-human")
async def request_human(conv_id: int, body: RequestHumanIn, request: Request) -> dict[str, Any]:
    user_type, subject_id = await resolve_identity(request)
    if user_type == USER_TYPE_GUEST:
        raise HTTPException(403, "请先在 APP 内登录后再转接人工客服")
    conv = await conv_dao.get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")
    mode, _ = await conv_dao.get_mode(conv_id)
    if mode == "human_takeover":
        return {"ok": True, "note": "already human-handled"}
    await conv_dao.set_mode(conv_id, "human_pending")
    await refresh_human_pending()
    # 转人工时按路由规则匹配 target_group_id（失败不阻塞主流程，仅记日志）
    try:
        await routing_rules.route_conversation_now(conv_id=conv_id, user_type=user_type)
    except Exception:
        logging.getLogger(__name__).exception(
            "route_conversation_now failed (conv_id=%s)", conv_id
        )
    out = await create_ticket_run(
        subject_id=subject_id,
        user_type=user_type,
        conversation_id=conv_id,
        category="人工介入",
        summary=f"用户请求人工：{body.reason or '(no reason)'}",
        severity="p2",
        evidence={"conversation_id": conv_id, "reason": body.reason},
    )
    _publish(conv_id, {"type": "request_human", "ticket_id": out["external_ticket_id"]})
    return {"ok": True, "ticket_id": out["external_ticket_id"]}


class UserEventIn(BaseModel):
    event: str  # "user_confirmed_resolved" | "user_rejected_resolved"
    reason: str | None = None


@router.post("/api/v1/tickets/{external_id}/user-events")
async def user_events(external_id: str, body: UserEventIn, request: Request) -> dict[str, Any]:
    user_type, subject_id = await resolve_identity(request)

    t = await ticket_dao.get_ticket(external_id)
    if not t:
        raise HTTPException(404, "ticket not found")
    payload = json.loads(str(t["payload_json"]))
    payload_subject = payload.get("bu_id") if user_type == "b" else payload.get("user_id")
    if payload_subject != subject_id:
        raise HTTPException(403, "not your ticket")

    if body.event == "user_confirmed_resolved":
        metrics.user_resolved_total.labels(event=body.event).inc()
        await ticket_dao.append_ticket_event(
            external_id, "closed", "user", "用户确认已解决", raw={"source": "user"}
        )
        await push_event_center(
            {"external_ticket_id": external_id, "event": "closed", "actor": "user"}
        )
        return {"ok": True}

    if body.event == "user_rejected_resolved":
        metrics.user_resolved_total.labels(event=body.event).inc()
        await ticket_dao.append_ticket_event(
            external_id,
            "reopen",
            "user",
            body.reason or "用户表示未解决",
            raw={"source": "user", "reason": body.reason},
        )
        await push_event_center(
            {
                "external_ticket_id": external_id,
                "event": "reopen",
                "actor": "user",
                "reason": body.reason,
            }
        )
        return {"ok": True}

    raise HTTPException(400, "unknown event")
