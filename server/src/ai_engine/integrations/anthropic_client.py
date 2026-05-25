from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from ai_engine.config import settings

# base_url 为 None 时 SDK 默认连官方 api.anthropic.com;
# 设了就走公司自建网关
def _build_client() -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,  # None => SDK 用默认
        max_retries=settings.anthropic_max_retries,  # 显式重试（指数退避）
        timeout=settings.anthropic_timeout_seconds,  # 显式超时，避免默认 600s
    )


_client = _build_client()


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


_CLASSIFY_SYSTEM = (
    "Classify if the user message is about Tevau "
    "(APP / Open API / card / account / order / bug). "
    "Reply with exactly one word: yes / no / uncertain."
)


async def classify_topic(message: str) -> str:
    """spec §6.4 第二层：haiku 意图分类，返回模型原始单词文本（调用方解析）。"""
    resp = await _client.messages.create(
        model=settings.summary_model,
        max_tokens=10,
        stop_sequences=["\n"],
        system=_CLASSIFY_SYSTEM,
        messages=[{"role": "user", "content": message}],
    )
    parts = [getattr(b, "text", "") for b in getattr(resp, "content", [])]
    return "".join(parts).strip().lower()


async def stream_text_only(request_body: dict[str, object]) -> AsyncIterator[str]:
    """只 yield 文本增量。给后续 agent runtime 用 stream 的复杂版替换。"""
    async with _client.messages.stream(**request_body) as stream:  # type: ignore[arg-type]
        async for ev in stream:
            if getattr(ev, "type", None) == "content_block_delta":
                delta = getattr(ev, "delta", None)
                if delta and getattr(delta, "type", None) == "text_delta":
                    yield delta.text
