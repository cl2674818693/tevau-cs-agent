import hashlib
import hmac
import json
from typing import Any

import httpx

from ai_engine.config import settings


def _sign(body: bytes) -> str:
    return hmac.new(settings.event_center_secret.encode(), body, hashlib.sha256).hexdigest()


async def push_event_center(payload: dict[str, Any]) -> bool:
    """HMAC 签名推送事件到事项中心（closed / reopen / 用户确认）。失败返回 False，不抛。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-Signature": _sign(body), "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{settings.event_center_url}/events", content=body, headers=headers
            )
        return 200 <= resp.status_code < 300
    except Exception:
        return False
