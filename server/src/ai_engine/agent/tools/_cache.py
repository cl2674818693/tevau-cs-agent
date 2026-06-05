"""工具结果短缓存（spec §11 性能治理）。

仅对 query_* 只读工具生效；create_ticket / mutating 工具一律穿透。
Redis 不可达或未配置时直接穿透（fail-open），不影响业务。
缓存 key = sha256(tool_name | subject_id | sorted_params)；value = json，
TTL = settings.tool_cache_ttl_seconds。
"""
import hashlib
import json
import logging
from typing import Any

from ai_engine.config import settings
from ai_engine.governance import rate_limit  # 复用其 redis client（避免双连）

logger = logging.getLogger(__name__)


def is_cacheable(tool_name: str) -> bool:
    """只对查询类工具启用缓存。"""
    return tool_name.startswith("query_")


def _key(tool_name: str, params: dict[str, Any], subject_id: str) -> str:
    # default=str 兜底 Decimal / datetime 等不可序列化对象（params 大多是 str/int，但稳健点）
    canon = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.sha256(f"{tool_name}|{subject_id}|{canon}".encode()).hexdigest()[:24]
    return f"cs:tool:{tool_name}:{h}"


async def get(tool_name: str, params: dict[str, Any], subject_id: str) -> dict[str, Any] | None:
    """命中返回缓存值（{"ok": True, "data": ...} 形态）；未命中或不缓存返回 None。"""
    if settings.tool_cache_ttl_seconds <= 0 or not is_cacheable(tool_name):
        return None
    redis = rate_limit._get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(_key(tool_name, params, subject_id))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("tool cache get failed", exc_info=True)
        return None


async def set_(
    tool_name: str, params: dict[str, Any], subject_id: str, result: dict[str, Any]
) -> None:
    """缓存成功结果；失败结果 / 非 query_* 工具一律跳过。"""
    if settings.tool_cache_ttl_seconds <= 0 or not is_cacheable(tool_name):
        return
    if not result.get("ok"):
        return  # 失败不缓存，让下次重试
    redis = rate_limit._get_redis()
    if redis is None:
        return
    try:
        await redis.set(
            _key(tool_name, params, subject_id),
            json.dumps(result, ensure_ascii=False, default=str),
            ex=settings.tool_cache_ttl_seconds,
        )
    except Exception:
        logger.warning("tool cache set failed", exc_info=True)
