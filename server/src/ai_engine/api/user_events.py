import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.agent.tools.create_ticket import run as create_ticket_run
from ai_engine.api.staff_conversations import _publish
from ai_engine.auth.bu_session import USER_TYPE_GUEST, resolve_identity
from ai_engine.i18n import t as _t
from ai_engine.observability import metrics
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db
from ai_engine.persistence import tickets as ticket_dao
from ai_engine.persistence.staff_metrics import refresh_human_pending
from ai_engine.services.dispatch import dispatch_to_human_pending

router = APIRouter()


class RequestHumanIn(BaseModel):
    reason: str | None = None
    ui_locale: str | None = None  # APP 当前语言（bridge.getEnv().language），决定 403 文案语种


@router.post("/api/v1/conversations/{conv_id}/request-human")
async def request_human(conv_id: int, body: RequestHumanIn, request: Request) -> dict[str, Any]:
    user_type, subject_id = await resolve_identity(request)
    if user_type == USER_TYPE_GUEST:
        raise HTTPException(403, _t("handoff.guest_blocked", body.ui_locale))
    conv = await conv_dao.get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")

    mode, _ = await conv_dao.get_mode(conv_id)
    if mode == "human_takeover":
        return {"ok": True, "note": "already human-handled", "no_one_online": False}

    if mode == "human_pending":
        row = await db.fetch_one(
            "SELECT external_id FROM tickets WHERE conversation_id = :cid "
            "ORDER BY created_at DESC LIMIT 1",
            {"cid": conv_id},
        )
        existing_ticket = str(row["external_id"]) if row else None
        result = await dispatch_to_human_pending(conv_id)
        return {
            "ok": True,
            "status": "already_pending",
            "ticket_id": existing_ticket,
            "note": "already pending human takeover",
            "no_one_online": bool(result.get("no_one_online")),
        }

    await conv_dao.set_mode(conv_id, "human_pending")
    await refresh_human_pending()
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
    return {
        "ok": True,
        "ticket_id": out["external_ticket_id"],
        "no_one_online": bool(out.get("no_one_online")),
    }


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

    # 事项中心契约：cs-engine 不再外推 closed/reopen 事件——事项中心是工单状态真源，
    # 用户在 cs-engine 内的"已解决/未解决"回执只落本地（admin 后台可见 + 本地 metric），
    # 不主动反馈给事项中心。后续真要双向回执需对事项中心团队加新事件类型。
    if body.event == "user_confirmed_resolved":
        metrics.user_resolved_total.labels(event=body.event).inc()
        await ticket_dao.append_ticket_event(
            external_id, "closed", "user", "用户确认已解决", raw={"source": "user"}
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
        return {"ok": True}

    raise HTTPException(400, "unknown event")


class ClientInfoIn(BaseModel):
    platform: str | None = None
    app_version: str | None = None
    user_agent: str | None = None


@router.post("/api/v1/conversations/{conv_id}/client-info")
async def report_client_info(
    conv_id: int, body: ClientInfoIn, request: Request
) -> dict[str, Any]:
    """H5 端通过 bridge.getEnv() + navigator.userAgent 拿到的客户端环境上报。
    admin 详情页"会话信息"卡据此展示用户的平台/APP 版本，便于排查"是不是某版本 bug"。
    幂等：同会话 upsert，多次调用最新覆盖。鉴权按会话归属（不限 user/guest）。"""
    user_type, subject_id = await resolve_identity(request)
    conv = await conv_dao.get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")
    from ai_engine.persistence import client_info as ci_dao

    await ci_dao.upsert_client_info(
        conv_id, body.platform, body.app_version, body.user_agent
    )
    return {"ok": True}
