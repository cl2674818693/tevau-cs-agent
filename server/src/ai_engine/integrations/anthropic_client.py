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


# Anthropic 限制：整请求最多 4 个带 cache_control 的块。system 块里稳定提示前缀在前、
# 每轮可能变的动态块（语言兜底/uncertain 提示）在后追加，故只给前 4 个块打缓存断点。
# 游客回合 system 块会达 5 个（3 基础 + 1 游客约束 + 1 语言兜底），全打会 400。
_MAX_CACHE_BLOCKS = 4


def build_messages_request(
    *,
    system_blocks: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model: str,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """构造 Anthropic Messages API 请求体；对前 _MAX_CACHE_BLOCKS 个 system 块加 ephemeral
    cache_control（受 Anthropic「最多 4 个 cache_control 块」限制），其余块原样下发。"""
    cached_system = [
        {**blk, "cache_control": {"type": "ephemeral"}} if i < _MAX_CACHE_BLOCKS else blk
        for i, blk in enumerate(system_blocks)
    ]
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


async def stream_turn(request_body: dict[str, object]) -> AsyncIterator[dict[str, Any]]:
    """流式跑一轮 LLM。先逐段 yield {"text_delta": str} 文本增量，最后 yield {"final": Message}。

    runtime 据此实现真 token 流式：最终回复轮把增量实时推给用户；预自检/工具轮先缓冲。
    {"final"} 携带完整消息（content / stop_reason / usage），供记账、工具判定、落库。
    """
    async with _client.messages.stream(**request_body) as stream:  # type: ignore[arg-type]
        async for text in stream.text_stream:
            yield {"text_delta": text}
        final = await stream.get_final_message()
    yield {"final": final}
