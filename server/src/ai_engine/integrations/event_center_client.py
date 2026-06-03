"""事项中心出站客户端（HTTP POST + Bearer Authorization）。

事项中心契约（docs/event-center-onboarding.md）：
- POST {settings.event_center_url}（如 http://192.168.2.6:922/api/tasks）
- Authorization: Bearer {settings.event_center_token}
- body 详见 create_task()
- 响应 2xx 即视为接收成功；非 2xx 由 caller 决定兜底（如 Lark 告警）。

只暴露一个 create_task()——所有需要主动推事项中心的场景（建工单 / SLA 升级 / 后续新事件类型）都走它，避免请求构造逻辑散落到各处。
"""

import logging
from typing import Any

import httpx

from ai_engine.config import settings

logger = logging.getLogger(__name__)


async def create_task(
    *,
    event_id: str,
    context: str,
    priority: int,
    action_type: str = "task",
    entities: list[dict[str, str]] | None = None,
    source_ref: str | None = None,
) -> bool:
    """按事项中心契约推送一条事项。返回 True/False。

    Args:
        event_id: 幂等键（同一 id 重推 → 事项中心返回已有事项 is_new=false）。
                  cs-engine 内通常用 ticket external_id 或语义化 key（如 "timeout-{cid}"）。
        context: 自然语言描述（50-200 字），事项中心会基于此生成 title。
        priority: 1=低 2=普通 3=高 4=紧急。
        action_type: "task"=需要人处理 / "notify"=仅记录。
        entities: [{type, id, name?}]，关联的业务对象（customer/partner/card/transaction）。
        source_ref: cs-engine 内部稳定引用 ID，方便事项中心运营反向跳回。
    """
    body: dict[str, Any] = {
        "event_id": event_id,
        "action_type": action_type,
        "source_module": "ticket",
        "event_type": "new_ticket",
        "context": context,
        "priority": priority,
        "entities": entities or [],
        "source_ref": source_ref,
        "callback_url": settings.event_center_callback_url or None,
    }
    headers = {"Content-Type": "application/json"}
    if settings.event_center_token:
        headers["Authorization"] = f"Bearer {settings.event_center_token}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(settings.event_center_url, json=body, headers=headers)
        if not 200 <= resp.status_code < 300:
            logger.warning(
                "event_center create_task non-2xx: status=%s event_id=%s",
                resp.status_code,
                event_id,
            )
            return False
        return True
    except Exception:
        logger.warning("event_center create_task failed (event_id=%s)", event_id, exc_info=True)
        return False
