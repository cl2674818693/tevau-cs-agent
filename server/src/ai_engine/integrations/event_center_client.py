import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from ai_engine.config import settings

logger = logging.getLogger(__name__)


def _sign(body: bytes) -> str:
    # 出口签名用 current key（spec §7.4 双 key 轮换）
    return hmac.new(settings.event_center_secret_current.encode(), body, hashlib.sha256).hexdigest()


async def push_event_center(payload: dict[str, Any]) -> bool:
    """HMAC 签名推送事件到事项中心（closed / reopen / 用户确认）。失败返回 False，不抛。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"X-Signature": _sign(body), "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{settings.event_center_url}/events", content=body, headers=headers
            )
        if not 200 <= resp.status_code < 300:
            logger.warning(
                "event_center push non-2xx: status=%s type=%s",
                resp.status_code,
                payload.get("type"),
            )
            return False
        return True
    except Exception:
        # 不抛、返回 False 不变；但记录便于排障（外部回调失败会静默丢事件）
        logger.warning("event_center push failed (type=%s)", payload.get("type"), exc_info=True)
        return False
