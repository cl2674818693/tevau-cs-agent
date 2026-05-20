from typing import Any

import httpx

from ai_engine.config import settings


async def send(payload: dict[str, Any]) -> None:
    if not settings.lark_webhook_url:
        return
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            settings.lark_webhook_url,
            json={
                "msg_type": "text",
                "content": {"text": payload.get("text", "工单兜底通知")},
            },
        )
