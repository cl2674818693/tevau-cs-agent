import asyncio
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from ai_engine.config import settings
from ai_engine.observability import metrics


class SystemBusy(Exception):
    """LLM 调用信号量超载——所有 worker 都满了，建议前端稍后重试。"""


# base_url 为 None 时 SDK 默认连官方 api.anthropic.com;
# 设了就走公司自建网关
def _build_client() -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
        max_retries=settings.anthropic_max_retries,
        timeout=settings.anthropic_timeout_seconds,
    )


_client = _build_client()

# 进程内 LLM 调用信号量。超载时不阻塞用户长 wait，acquire 超时直接 SystemBusy。
# asyncio.Semaphore 绑定到创建它的事件循环；生产只一个 loop，所以一次创建够用。
# 测试每个用例新建 loop（pytest-asyncio function scope），所以按 loop 缓存 sem。
_llm_sems: "dict[asyncio.AbstractEventLoop, asyncio.Semaphore]" = {}


def _rebuild_llm_semaphore() -> None:
    """测试 monkeypatch settings 后清掉所有 loop 的缓存；下次访问时按当前 loop 重建。"""
    _llm_sems.clear()


def _get_sem() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _llm_sems.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(int(settings.llm_max_concurrency))
        _llm_sems[loop] = sem
    return sem


async def _acquire_or_busy() -> None:
    sem = _get_sem()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=settings.llm_acquire_timeout_seconds)
    except asyncio.TimeoutError as e:
        metrics.llm_busy_rejections_total.inc()
        raise SystemBusy("LLM concurrency limit reached") from e
    metrics.llm_inflight.inc()


def _release() -> None:
    _get_sem().release()
    metrics.llm_inflight.dec()


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
    tool_choice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造 Anthropic Messages API 请求体；对前 _MAX_CACHE_BLOCKS 个 system 块加 ephemeral
    cache_control（受 Anthropic「最多 4 个 cache_control 块」限制），其余块原样下发。

    tool_choice：传 {"type":"none"} 强制本轮不调工具（self-check 修订轮专用，防回复重复）。
    """
    cached_system = [
        {**blk, "cache_control": {"type": "ephemeral"}} if i < _MAX_CACHE_BLOCKS else blk
        for i, blk in enumerate(system_blocks)
    ]
    req: dict[str, Any] = {
        "model": model,
        "system": cached_system,
        "messages": messages,
        "tools": tools or [],
        "max_tokens": max_tokens,
    }
    if tool_choice is not None:
        req["tool_choice"] = tool_choice
    return req


_CLASSIFY_SYSTEM = (
    "Classify if the user message is about Tevau "
    "(APP / Open API / card / account / order / bug). "
    "Reply with exactly one word: yes / no / uncertain."
)


async def classify_topic(message: str) -> str:
    """spec §6.4 第二层：haiku 意图分类，返回模型原始单词文本（调用方解析）。"""
    await _acquire_or_busy()
    try:
        resp = await _client.messages.create(
            model=settings.summary_model,
            max_tokens=10,
            stop_sequences=["\n"],
            system=_CLASSIFY_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
    finally:
        _release()
    parts = [getattr(b, "text", "") for b in getattr(resp, "content", [])]
    return "".join(parts).strip().lower()


async def stream_turn(request_body: dict[str, object]) -> AsyncIterator[dict[str, Any]]:
    """流式跑一轮 LLM。先逐段 yield {"text_delta": str} 文本增量，最后 yield {"final": Message}。

    被外层 CancelledError 时 async with 自动 aclose 上游 HTTP，
    保证客户端断开后 token 不再继续消耗。

    runtime 据此实现真 token 流式：最终回复轮把增量实时推给用户；预自检/工具轮先缓冲。
    {"final"} 携带完整消息（content / stop_reason / usage），供记账、工具判定、落库。
    """
    await _acquire_or_busy()
    try:
        async with _client.messages.stream(**request_body) as stream:  # type: ignore[arg-type]
            async for text in stream.text_stream:
                yield {"text_delta": text}
            final = await stream.get_final_message()
        yield {"final": final}
    finally:
        _release()
