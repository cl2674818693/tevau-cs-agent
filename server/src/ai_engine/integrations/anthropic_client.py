from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from ai_engine.config import settings

# base_url 为 None 时 SDK 默认连官方 api.anthropic.com;
# 设了就走公司自建网关
_client = AsyncAnthropic(
    api_key=settings.anthropic_api_key,
    base_url=settings.anthropic_base_url,  # None => SDK 用默认
)


def build_messages_request(
    *,
    system_blocks: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model: str,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """构造 Anthropic Messages API 请求体, 对每个 system 块加 ephemeral cache_control。"""
    cached_system = []
    for blk in system_blocks:
        cached_system.append({**blk, "cache_control": {"type": "ephemeral"}})
    return {
        "model": model,
        "system": cached_system,
        "messages": messages,
        "tools": tools or [],
        "max_tokens": max_tokens,
    }


async def stream_text_only(request_body: dict[str, object]) -> AsyncIterator[str]:
    """只 yield 文本增量。给后续 agent runtime 用 stream 的复杂版替换。"""
    async with _client.messages.stream(**request_body) as stream:  # type: ignore[arg-type]
        async for ev in stream:
            if getattr(ev, "type", None) == "content_block_delta":
                delta = getattr(ev, "delta", None)
                if delta and getattr(delta, "type", None) == "text_delta":
                    yield delta.text
