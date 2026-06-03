"""事项中心 → cs-engine 结案回调（替代旧 HMAC 入站端点）。

事项中心契约（docs/event-center-onboarding.md §九）：工单结案后 POST 到 callback_url
（即此端点），body 含 status=completed + resolution + handled_by + resolve_seconds 等。
按约定 cs-engine 返回 2xx 即视为接收成功，失败时事项中心重试 3 次。

cs-engine 收到后：
1. Bearer token 验签（防公网伪造）
2. 用 event_id（=external_id）定位本地 ticket
3. 落 ticket_events 表（event="closed"，因为事项中心 status=completed 在 cs-engine 语义下 = 关闭）
4. 推 SSE 到该会话的 ticket-events-stream，前端会话界面看到工单关闭事件
5. 入解决耗时 metric
"""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ai_engine.api.staff_conversations import _publish
from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence.tickets import append_ticket_event, get_ticket

router = APIRouter()


class EventCenterCallback(BaseModel):
    """事项中心结案回调 body（按 integration-guide §九）。
    严格用 pydantic 校验，缺字段 / 类型错 → 400，让事项中心团队联调时拿到清晰错误。"""

    task_id: int | str = Field(description="事项中心分配的事项 ID")
    event_id: str = Field(min_length=1, description="cs-engine 当时上送的 external_id")
    source_ref: str | None = None
    event_type: str | None = None  # 当前只有 new_ticket
    status: str = Field(description="事项中心当前只发 completed；预留 cancelled 等")
    resolution: str | None = None  # 客服处理摘要
    resolution_type: str | None = None  # 如 manual_correction / closed_no_action
    handled_by: str | None = None  # 客服显示名
    created_at: str | None = None
    resolved_at: str | None = None
    response_seconds: int | None = None
    resolve_seconds: int | None = None


def _require_callback_token(authorization: str) -> None:
    """Bearer 验签：与 EVENT_CENTER_CALLBACK_TOKEN 比对，不一致 401。
    callback_token 为空时拒所有调用（防漏配 token 时 callback 端点裸奔）。"""
    expected = settings.event_center_callback_token
    if not expected:
        raise HTTPException(503, "callback token not configured; refuse all inbound")
    prefix = "Bearer "
    if not authorization.startswith(prefix) or authorization[len(prefix):] != expected:
        raise HTTPException(401, "bad authorization")


@router.post("/api/v1/event-center/callback")
async def callback(
    request: Request,
    body: EventCenterCallback,
    authorization: str = Header(default=""),
) -> dict[str, bool]:
    _require_callback_token(authorization)

    ticket = await get_ticket(body.event_id)
    if ticket is None:
        # 事项中心拿到不存在的 event_id 是异常（应该是创建时的同一 id 才对）；
        # 返 404 让对端定位问题，不要静默吞下避免漏 bug
        raise HTTPException(404, f"ticket {body.event_id} not found locally")

    # 事项中心 status=completed → cs-engine 语义下 = closed（最终关闭）。
    # 预留：未来事项中心扩支持 cancelled / escalated 等再加分支。
    event_name = "closed" if body.status == "completed" else body.status

    raw_bytes = await request.body()
    try:
        raw_parsed: dict[str, Any] = json.loads(raw_bytes) if raw_bytes else {}
    except json.JSONDecodeError:
        raw_parsed = {"raw_body_unparsable": True}

    await append_ticket_event(
        external_id=body.event_id,
        event=event_name,
        actor=body.handled_by,
        comment=body.resolution,
        raw=raw_parsed,
    )

    # 推 SSE 给用户会话（前端会话页 ticket-events-stream 订阅）
    _publish(
        int(ticket["conversation_id"]),  # type: ignore[call-overload]
        {
            "type": event_name,
            "external_id": body.event_id,
            "actor": body.handled_by,
            "comment": body.resolution,
        },
    )

    # 解决耗时入 metric（事项中心 resolve_seconds 直接可用，避免本地算时差）
    if event_name == "closed":
        payload_json = ticket.get("payload_json", "{}")
        try:
            category = str(json.loads(str(payload_json)).get("category", "unknown"))
        except json.JSONDecodeError:
            category = "unknown"
        elapsed = body.resolve_seconds
        if elapsed is None:
            # fallback：用本地 created_at 算到现在的耗时（兜底，事项中心没传 resolve_seconds 时）
            try:
                created = datetime.fromisoformat(str(ticket["created_at"]))
                elapsed = int((datetime.now(UTC).replace(tzinfo=None) - created).total_seconds())
            except (ValueError, KeyError, TypeError):
                elapsed = None
        if elapsed is not None and elapsed >= 0:
            metrics.ticket_resolution_seconds.labels(category=category).observe(elapsed)

    return {"ok": True}
