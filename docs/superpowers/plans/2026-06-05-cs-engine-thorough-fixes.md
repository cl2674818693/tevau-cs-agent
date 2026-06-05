# CS-Engine 四问彻底化方案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把先前 4 个问题（并发承载 / SSE 中断 / 查库慢 / 节点架构）的 P0+P1 项一次性落到代码里，让线上能扛 1000+ 在线 + 工具响应砍半 + 流被取消时不再烧 token。

**Architecture:** 全部改动在 `server/src/ai_engine/` 之下，分四块：(1) LLM 调用层加 Semaphore + 让 stream 可被取消；(2) chat.py SSE 检测 client disconnect 并 set cancel_evt；(3) `_run_tools` 改 `asyncio.gather` 并发 + 两个 N+1 工具改 IN 批查；(4) 工具结果按 (tool, normalized_args, subject_id) 走 Redis 缓存；(5) topic_classifier 对已绑定身份用户跳过；(6) Dockerfile 多 worker + 新指标。前端 / 多 provider / read replica / eval 集 4 项标记为"超出本计划范围"。

**Tech Stack:** Python 3.12, FastAPI, sse-starlette, anthropic AsyncAnthropic, aiomysql, asyncpg, redis-py (已经在用), prometheus_client, pytest.

**out-of-scope（需另起 plan 或人工决策）：**
- 前端心跳回信（需 H5 + 后端联调）
- k8s 水平扩 / 多 LLM provider 兜底（基建决策）
- 业务库 read replica（DBA + 业务库团队）
- 灰度看板 / eval 评测集（数据 + 标注资源）

---

## Task 1: LLM 调用层 Semaphore + 可取消流

**目的**：anthropic_client 拿不到信号量时快速失败，stream 在被外层 cancel 时上游 HTTP 立即关闭，token 不再烧。

**Files:**
- Modify: `server/src/ai_engine/integrations/anthropic_client.py`
- Modify: `server/src/ai_engine/config.py:73` 区域（加配置项）
- Modify: `server/src/ai_engine/observability/metrics.py`（加 Semaphore 指标）
- Create: `server/tests/unit/test_anthropic_semaphore.py`

- [ ] **Step 1: 写失败测试 — Semaphore 超载快失败**

新建 `server/tests/unit/test_anthropic_semaphore.py`：

```python
"""Anthropic 调用 Semaphore 护栏。

超载场景：信号量为 1 时，第 2 个并发调用必须在 acquire 超时（settings.llm_acquire_timeout）
内返回 SystemBusy 异常，而不是阻塞等待 LLM 调用本身。
"""
import asyncio
import pytest

from ai_engine.integrations import anthropic_client as ac
from ai_engine.config import settings


class SystemBusy(Exception):
    """Semaphore 超载时抛出。"""


@pytest.fixture(autouse=True)
def _tight_sem(monkeypatch):
    monkeypatch.setattr(settings, "llm_max_concurrency", 1, raising=False)
    monkeypatch.setattr(settings, "llm_acquire_timeout_seconds", 0.05, raising=False)
    # 重建 semaphore（运行时模块级 _llm_sem）
    ac._rebuild_llm_semaphore()
    yield


async def test_semaphore_busy_raises_quickly(monkeypatch):
    # 准备一个会阻塞 1s 的 fake stream
    async def slow_stream(text):
        await asyncio.sleep(1.0)
        return "yes"

    monkeypatch.setattr(ac._client.messages, "create", lambda **_: slow_stream(""))

    async def call():
        return await ac.classify_topic("hello")

    # 启动第一个调用（占住信号量）
    first = asyncio.create_task(call())
    await asyncio.sleep(0.01)
    # 第二个必须在 ~50ms 内拿不到信号量并抛错
    with pytest.raises(ac.SystemBusy):
        await call()
    first.cancel()
```

- [ ] **Step 2: 跑测试看红**

```bash
cd server && uv run pytest tests/unit/test_anthropic_semaphore.py -v
```

Expected: FAIL — `AttributeError: module 'ai_engine.integrations.anthropic_client' has no attribute 'SystemBusy'`。

- [ ] **Step 3: config.py 加配置项**

在 `server/src/ai_engine/config.py` 的 `daily_token_limit` 后面（约 60 行附近）加：

```python
    # LLM 并发护栏：单进程内同时进行的 LLM 调用上限（含 stream + classify）。
    # 多 worker 时全局并发 = workers × llm_max_concurrency。超载快失败 → 用户看到 system_busy 提示。
    llm_max_concurrency: int = 20
    # 拿不到信号量的等待时长；超过即视为系统繁忙，避免 SSE 长时间挂起
    llm_acquire_timeout_seconds: float = 0.5
```

- [ ] **Step 4: anthropic_client.py 实现 Semaphore + SystemBusy + 可取消 stream**

将 `server/src/ai_engine/integrations/anthropic_client.py` 整体改写为：

```python
import asyncio
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from ai_engine.config import settings
from ai_engine.observability import metrics


class SystemBusy(Exception):
    """LLM 调用信号量超载——所有 worker 都满了，建议前端稍后重试。"""


def _build_client() -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
        max_retries=settings.anthropic_max_retries,
        timeout=settings.anthropic_timeout_seconds,
    )


_client = _build_client()

# 进程内 LLM 调用信号量。超载时不阻塞用户长 wait，acquire 超时直接 SystemBusy。
_llm_sem: asyncio.Semaphore | None = None


def _rebuild_llm_semaphore() -> None:
    """测试 monkeypatch settings 后用。生产只在模块首次访问时建一次。"""
    global _llm_sem
    _llm_sem = asyncio.Semaphore(int(settings.llm_max_concurrency))


def _get_sem() -> asyncio.Semaphore:
    global _llm_sem
    if _llm_sem is None:
        _rebuild_llm_semaphore()
    return _llm_sem  # type: ignore[return-value]


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
    """流式跑一轮 LLM。被外层 CancelledError 时 async with 自动 aclose 上游 HTTP，
    保证客户端断开后 token 不再继续消耗。
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
```

- [ ] **Step 5: metrics.py 加新指标**

在 `server/src/ai_engine/observability/metrics.py` 末尾追加：

```python
# LLM 并发护栏
llm_inflight = Gauge("ai_engine_llm_inflight", "进行中的 LLM 调用数（含 stream + classify）")
llm_busy_rejections_total = Counter(
    "ai_engine_llm_busy_rejections_total", "因 Semaphore 满拒绝的 LLM 调用次数"
)
```

- [ ] **Step 6: 跑测试看绿**

```bash
cd server && uv run pytest tests/unit/test_anthropic_semaphore.py -v
```

Expected: PASS（两个 case：busy 超时抛 SystemBusy + 释放后再次可用——若只写了一个则补另一个）。

补一个释放-再获取测试在同一文件：

```python
async def test_semaphore_release_allows_next(monkeypatch):
    async def quick(text):
        return "yes"
    monkeypatch.setattr(ac._client.messages, "create", lambda **_: quick(""))
    # 第一个跑完释放，第二个能拿到
    r1 = await ac.classify_topic("a")
    r2 = await ac.classify_topic("b")
    assert r1 == "yes" and r2 == "yes"
```

- [ ] **Step 7: 跑全部 anthropic_client 相关测试**

```bash
cd server && uv run pytest tests/unit/test_integrations_anthropic_client.py tests/agent/test_anthropic_client_config.py tests/unit/test_anthropic_semaphore.py -v
```

Expected: 全 PASS。如有旧测试因 monkeypatch `_client.messages.stream` 直接 break 了 `async with`，把那些测试的 stream context manager 也对齐到新签名。

- [ ] **Step 8: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/integrations/anthropic_client.py \
          server/src/ai_engine/observability/metrics.py \
          server/src/ai_engine/config.py \
          server/tests/unit/test_anthropic_semaphore.py && \
  git commit -m "feat(llm): semaphore guard + cancel-safe stream

进程内并发上限 settings.llm_max_concurrency=20，超载 0.5s 内抛 SystemBusy；
stream 用 async with 包，外层 CancelledError 时自动 aclose 上游 HTTP，避免
客户端断开后 token 继续烧。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: chat.py 监听 client disconnect 并传播 cancel

**目的**：用户关掉 webview / 网络断时，后端 SSE generator 检测 `request.is_disconnected()`，set cancel_evt，runtime.run_turn 上抛 CancelledError，Anthropic stream 经 Task 1 的 async with 关掉。

**Files:**
- Modify: `server/src/ai_engine/api/chat.py:215-292`（gen 块 + finally）
- Modify: `server/src/ai_engine/api/chat.py:158-196`（_stream_ai_turn）
- Create: `server/tests/agent/test_chat_disconnect_cancels.py`

- [ ] **Step 1: 写失败测试**

新建 `server/tests/agent/test_chat_disconnect_cancels.py`：

```python
"""client 断开后，正在跑的 runtime.run_turn 被 cancel；finally 块清理 _cancel_signals。

不依赖真 LLM：runtime.run_turn 用 fake async generator 替换。
"""
import asyncio
import pytest

from ai_engine.api import chat as chat_api


@pytest.fixture
def fake_request(monkeypatch):
    class _Req:
        disconnected = False
        client = type("c", (), {"host": "127.0.0.1"})()
        async def is_disconnected(self):
            return self.disconnected
    return _Req()


async def test_disconnect_sets_cancel_signal(monkeypatch, fake_request):
    triggered = asyncio.Event()

    async def fake_run_turn(**kwargs):  # noqa: ANN003
        try:
            for _ in range(100):
                yield {"type": "text", "text": "x"}
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            triggered.set()
            raise

    monkeypatch.setattr(chat_api.runtime, "run_turn", fake_run_turn)

    cancel_evt = asyncio.Event()
    gen = chat_api._stream_ai_turn(
        conversation_id=1, user_type="c", subject_id="U1",
        message="hi", client_message_id=None,
        cancel_evt=cancel_evt, attachment_ids=[], ui_locale=None,
    )

    async def drive():
        async for _ in gen:
            cancel_evt.set()  # 模拟用户/network 触发 cancel
            await asyncio.sleep(0)
            return

    await asyncio.wait_for(drive(), timeout=1.0)
    # cancel_evt 被 set 后 _stream_ai_turn 必须 yield message_stop(cancelled) 并停止
```

- [ ] **Step 2: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_chat_disconnect_cancels.py -v
```

Expected: PASS（当前 chat.py 已经有 cancel_evt 检测）—— 那这个测试只是"现状回归"。继续 Step 3 加 disconnect 检测真正缺的部分。

- [ ] **Step 3: chat.py:gen 内加 disconnect 检测协程**

在 `server/src/ai_engine/api/chat.py` 顶部 import 区域加：

```python
import contextlib
```

将 `chat()` 函数的 `gen()` 内层改造，加一个后台 disconnect 监听 task：

在 `chat.py:215` 的 `async def gen()` 起始处之前，新增一个辅助：

```python
async def _watch_disconnect(request: Request, cancel_evt: asyncio.Event) -> None:
    """周期性检测 client 是否断开；断开则 set cancel_evt 让 gen 链路立刻退出。

    sse_starlette 本身在 yield 时也会检测，但若 runtime 卡在 LLM 调用（非 yield 中），
    SSE 层察觉不到 client 已走 —— 这里 250ms 主动 poll 一次，覆盖该缝隙。
    """
    try:
        while not cancel_evt.is_set():
            if await request.is_disconnected():
                cancel_evt.set()
                return
            await asyncio.sleep(0.25)
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 4: 把 watch 接进 gen 里**

修改 `chat.py:215-293` 的 chat() 主体（保留 `_cancel_signals[conversation_id] = cancel_evt` 那行），在 `async def gen()` 里用 task 启动 watcher：

```python
    async def gen() -> AsyncIterator[dict[str, str]]:
        watcher = asyncio.create_task(_watch_disconnect(request, cancel_evt))
        try:
            yield se.sse_payload(
                se.EVENT_CONVERSATION,
                {
                    "conversation_id": conversation_id,
                    "user_type": user_type,
                    "model": "claude-sonnet-4-6",
                },
            )
            # ... (保留原 _early_block / dup / human_mode / budget / ai_draft / _stream_ai_turn 分支)
            # 全部保留原代码
        except Exception:
            logger.exception("chat stream failed (conversation_id=%s)", conversation_id)
            yield se.error_event("INTERNAL_ERROR", _t("error.internal", ui_locale))
        finally:
            cancel_evt.set()  # 兜底：确保 watcher / runtime 都收到 cancel
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
            _cancel_signals.pop(conversation_id, None)
```

- [ ] **Step 5: _stream_ai_turn 在 cancel 后 yield 一帧 message_stop**

当前 `chat.py:189-191` 已经有 cancel_evt 检测，但仅在 runtime 持续 yield 时才被检查到。runtime 卡在 LLM 调用中时 cancel 信号传不进去。

借助 Task 1 的可取消 stream，需要让 `_stream_ai_turn` 在 cancel_evt set 时主动停止 runtime async generator：

修改 `chat.py:180-196`：

```python
    async for ev in runtime.run_turn(
        conversation_id=conversation_id,
        user_type=user_type,
        subject_id=subject_id,
        user_message=message,
        client_message_id=client_message_id,
        attachment_ids=attachment_ids,
        ui_locale=ui_locale,
    ):
        if cancel_evt.is_set():
            yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "cancelled"})
            # runtime async gen 通过 GeneratorExit / aclose 收到取消
            return
        publish_conversation_event(conversation_id, _spectator_event(ev))
        mapped = _map_runtime_event(ev)
        if mapped is not None:
            yield mapped
    yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "end_turn"})
```

注：`return` 在 async generator 里会触发 `aclose()` 链路，runtime.run_turn 内部的 anthropic stream `async with` 自动关闭。

- [ ] **Step 6: 跑测试**

```bash
cd server && uv run pytest tests/agent/test_chat_disconnect_cancels.py tests/agent/test_runtime_streaming.py tests/agent/test_runtime_tool_loop.py -v
```

Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/api/chat.py server/tests/agent/test_chat_disconnect_cancels.py && \
  git commit -m "feat(sse): propagate client disconnect to runtime cancel

新增 _watch_disconnect 后台 task 250ms 轮询 request.is_disconnected()；断开即
set cancel_evt，_stream_ai_turn 主动 return 触发 runtime async gen aclose，链路
直达 anthropic stream 的 async with，上游 HTTP 立刻关闭。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: runtime._run_tools 串行 → 并发 gather

**目的**：LLM 同轮 emit 多个 tool_use 时并发执行而非串行 await，单轮工具响应砍 ~50%。

**Files:**
- Modify: `server/src/ai_engine/agent/runtime.py:600-654`
- Modify: `server/tests/agent/test_runtime_tool_loop.py`（加并发断言）

- [ ] **Step 1: 写测试 — 多工具调用应并发**

在 `server/tests/agent/test_runtime_tool_loop.py` 末尾追加：

```python
class TestParallelToolDispatch:
    """多个 tool_use 在同一轮中应并发执行（gather），总耗时 ≈ max(各工具) 而非 sum。"""

    async def test_tools_run_concurrently(
        self, monkeypatch, seeded_db, fake_stream, make_resp
    ) -> None:
        import time
        import asyncio
        from ai_engine.agent.tools import base as toolbase

        async def _slow_h(**kw):  # noqa: ANN003
            await asyncio.sleep(0.1)
            return {"ok": True, "tag": kw.get("tag")}

        for name in ("slow_a", "slow_b", "slow_c"):
            toolbase.register(
                toolbase.Tool(
                    name=name, description="slow",
                    input_schema={"type": "object", "properties": {"tag": {"type": "string"}}},
                    handler=_slow_h,
                )
            )

        responses = [
            make_resp(stop_reason="tool_use", tool_calls=[
                {"id": "t1", "name": "slow_a", "input": {"tag": "a"}},
                {"id": "t2", "name": "slow_b", "input": {"tag": "b"}},
                {"id": "t3", "name": "slow_c", "input": {"tag": "c"}},
            ]),
            make_resp(text="draft"),
            make_resp(text="done"),
        ]
        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream(responses))

        conv = await create_conversation("c", "U_PAR")
        t0 = time.monotonic()
        events = [e async for e in rt.run_turn(
            conversation_id=conv, user_type="c", subject_id="U_PAR", user_message="run",
        )]
        elapsed = time.monotonic() - t0

        for name in ("slow_a", "slow_b", "slow_c"):
            toolbase.REGISTRY.pop(name, None)

        # 串行需 ≥0.3s；并发应 ≤0.2s（含开销留余量）
        assert elapsed < 0.2, f"tools ran sequentially: {elapsed}s"
        # 3 个 tool_result 事件全到位
        assert sum(1 for e in events if e.get("type") == "tool_result") == 3
```

- [ ] **Step 2: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_runtime_tool_loop.py::TestParallelToolDispatch -v
```

Expected: FAIL — elapsed ~0.3s。

- [ ] **Step 3: runtime.py:_run_tools 改并发**

替换 `server/src/ai_engine/agent/runtime.py:600-654` 的 `_run_tools`：

```python
async def _run_tools(
    tool_calls: list[dict[str, Any]],
    guard: CostGuard,
    user_type: str,
    subject_id: str,
    conversation_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """执行本轮 tool_use，返回 (回灌给模型的 tool_result blocks, 流给前端的 tool_result 事件)。

    并发执行：LLM 同轮 emit 的多个 tool_use 之间无依赖（依赖会被 LLM 拆到下一轮再 call），
    用 asyncio.gather 并发执行。深度上限超出的 tool_call 直接生成 error block，不进 gather。
    """
    # 第一遍：分配 guard 配额，决定哪些 call 真跑 / 哪些挂 over-depth 错误
    runnable: list[tuple[int, dict[str, Any]]] = []
    blocks: list[dict[str, Any] | None] = [None] * len(tool_calls)
    for i, tc in enumerate(tool_calls):
        if not guard.can_call_again():
            blocks[i] = {
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": "ERROR: 达到工具调用深度上限，请直接给出当前结论或建工单。",
                "is_error": True,
            }
            continue
        guard.note_call()
        runnable.append((i, tc))

    async def _one(idx: int, tc: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
        r = await dispatch(
            tool_name=tc["name"],
            params=tc["input"],
            user_type=user_type,
            subject_id=subject_id,
            conversation_id=conversation_id,
        )
        payload = json.dumps(
            r.get("data") if r["ok"] else {"error": r["error"]}, ensure_ascii=False
        )
        payload, truncated = guard.maybe_truncate(payload)
        if truncated:
            payload += "\n[TRUNCATED]"
        block = {
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": payload,
            "is_error": not r["ok"],
        }
        result_count = _result_count(r.get("data")) if r["ok"] else 0
        event = {
            "type": "tool_result",
            "id": tc["id"],
            "name": tc["name"],
            "ok": r["ok"],
            "result_count": result_count,
            "empty": result_count == 0,
        }
        return idx, block, event

    # 并发执行所有 runnable tool calls；异常以 ok=False 兜底，不让单工具拖垮整轮
    results = await asyncio.gather(
        *[_one(idx, tc) for idx, tc in runnable],
        return_exceptions=True,
    )

    events: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, BaseException):
            # gather 捕到异常：找回对应 idx 是有点麻烦的；这里用最后一个未填的位置兜底
            # 实践中 dispatch 自己已经把异常封装为 r["ok"]=False，几乎不进这分支
            logger.warning("tool gather got exception: %r", item)
            continue
        idx, block, event = item
        blocks[idx] = block
        events.append(event)

    final_blocks = [b for b in blocks if b is not None]
    return final_blocks, events
```

需要在 runtime.py 顶部 import 加 `import asyncio`（如未有则补；当前文件已有 `from collections.abc import AsyncIterator`，没 import asyncio）。

```python
# runtime.py 顶部
import asyncio
```

- [ ] **Step 4: 跑测试看绿**

```bash
cd server && uv run pytest tests/agent/test_runtime_tool_loop.py -v
```

Expected: 全 PASS（含新增的并发断言）。

- [ ] **Step 5: 跑相关回归（self-check / max_depth / failsoft）**

```bash
cd server && uv run pytest tests/agent/test_runtime_self_check_tool_choice.py \
  tests/agent/test_runtime_max_depth.py tests/agent/test_runtime_failsoft.py -v
```

Expected: 全 PASS。max_depth 测试可能会因并发顺序乱序而需要小调（确认 blocks 的顺序仍按 tool_calls 输入顺序对齐——上面实现已经按 idx 对齐，应该没问题）。

- [ ] **Step 6: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/agent/runtime.py server/tests/agent/test_runtime_tool_loop.py && \
  git commit -m "perf(runtime): parallel tool dispatch via asyncio.gather

同轮 LLM emit 的多个 tool_use 之间无依赖，串行 await 改 gather；3 工具场景
总耗时从 sum 降到 max。深度上限超出的 call 不进 gather，直接生成 error block。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: query_card.py 消除 N+1

**目的**：当前每张冻结卡都查一次 FREEZE_SQL（N+1）；改成对所有冻结卡 IN 一次性批量查。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_card.py`
- Modify: `server/tests/agent/test_tool_query_card.py`

- [ ] **Step 1: 写失败测试 — 批量场景应只查 1 次冻结表**

在 `server/tests/agent/test_tool_query_card.py` 末尾追加：

```python
class TestBatchFreezeQuery:
    """多张冻结卡共用一次 FREEZE_SQL 批查（消除 N+1）。"""

    async def test_three_frozen_cards_one_freeze_query(self, fake_db) -> None:
        fake_db.cards = [
            {"id": 1, "card_number": "4938750672464590", "card_status": 9,
             "card_status_description": None, "card_balance": "0", "card_currency": 2,
             "card_type": 1, "expiry_date": None, "reject_reason": None,
             "cancel_card_reason": None, "card_alias_name": None,
             "active_time": None, "create_time": None},
            {"id": 2, "card_number": "4938750672464591", "card_status": 9,
             "card_status_description": None, "card_balance": "0", "card_currency": 2,
             "card_type": 1, "expiry_date": None, "reject_reason": None,
             "cancel_card_reason": None, "card_alias_name": None,
             "active_time": None, "create_time": None},
            {"id": 3, "card_number": "4938750672464592", "card_status": 2,
             "card_status_description": None, "card_balance": "0", "card_currency": 2,
             "card_type": 1, "expiry_date": None, "reject_reason": None,
             "cancel_card_reason": None, "card_alias_name": None,
             "active_time": None, "create_time": None},
        ]
        # 假冻结历史：id=1 → 4, id=2 → 1; id=3 无冻结历史
        fake_db.freezes = [
            {"target_id": 1, "freeze_reason": 4, "reason_desc": "人工",
             "create_time": "2026-01-01", "auto_unfreeze_time": None},
            {"target_id": 2, "freeze_reason": 1, "reason_desc": "黑名单",
             "create_time": "2026-01-02", "auto_unfreeze_time": None},
        ]
        out = await qc.run(user_id="1")
        # N+1 修复关键断言：只 1 次冻结表查询，不是 3 次
        assert fake_db.freeze_calls == 1, (
            f"freeze table queried {fake_db.freeze_calls} times; expected 1 (batched)"
        )
        # 每张卡的 freeze_reason 正确归属
        m = {c["card_id"]: c for c in out["cards"]}
        assert m[1]["freeze_reason"] == "人工冻结卡"
        assert m[2]["freeze_reason"] == "黑名单商户交易"
        assert "freeze_reason" not in m[3]  # 无冻结历史
```

同时改 `_FakeDB.fetch_all` 让批查 case 能按 SQL 关键字分发：当前 fixture 已经按 `"freeze_history" in sql` 分发，不用动；让 freezes 数据 mock 时多带个 `target_id` 字段，run() 实现用它分组即可。

- [ ] **Step 2: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_tool_query_card.py::TestBatchFreezeQuery -v
```

Expected: FAIL — freeze_calls=2 或 3。

- [ ] **Step 3: 改 query_card.py 用 IN 批查**

替换 `server/src/ai_engine/agent/tools/query_card.py:19-24` 的 `FREEZE_SQL` 和 `run()`：

```python
# 冻结历史表：按 user_id + target_id IN (...) + target_type=1(卡) 隔离，
# operation_type=1 取冻结记录。一次查回所有冻结卡的最新一条，避免 N+1。
# 注意 aiomysql 对 IN %s 接 tuple 的支持：传 ((c1, c2, c3),) 即可展开为 IN (c1,c2,c3)。
FREEZE_SQL = """
SELECT target_id, freeze_reason, reason_desc, create_time, auto_unfreeze_time
FROM t_tevaupay_bank_card_freeze_history
WHERE user_id=%s AND target_id IN %s AND target_type=1 AND operation_type=1 AND del=0
ORDER BY target_id, create_time DESC
"""


async def run(user_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前用户名下所有卡的状态（锁定/冻结看 status；冻结卡带出真实冻结原因；卡号脱敏，unmask 仅 engineer 代查）。

    N+1 消除：所有冻结/锁定卡的 freeze_history 一次 IN 批查，按 target_id 分组取最新。
    """
    db = get_db("unlimitpay")
    rows = await db.fetch_all(SQL, (user_id,), limit=20)
    # 一次性收集需要查冻结历史的卡 id
    frozen_ids = [r["id"] for r in rows if r.get("card_status") in _FROZEN_STATUSES]
    freeze_by_card: dict[Any, dict[str, Any]] = {}
    if frozen_ids:
        # aiomysql 占位符 IN 传 tuple of values；limit 给足覆盖 ORDER BY target_id 后每卡至少 1 条
        freezes = await db.fetch_all(
            FREEZE_SQL,
            (user_id, tuple(frozen_ids)),
            limit=len(frozen_ids) * 4,  # 每卡保留 ~4 条历史排序余量
        )
        # 按 target_id 分组，create_time DESC 排序后取第一条
        for fr in freezes:
            tid = fr.get("target_id")
            if tid not in freeze_by_card:
                freeze_by_card[tid] = fr

    cards = []
    for r in rows:
        view = _card_view(r, unmask)
        if r.get("card_status") in _FROZEN_STATUSES:
            fr = freeze_by_card.get(r["id"])
            if fr:
                view["freeze_reason"] = label(_FREEZE_REASON, fr.get("freeze_reason"))
                view["freeze_reason_code"] = fr.get("freeze_reason")
                view["freeze_reason_desc"] = fr.get("reason_desc")
                view["freeze_time"] = str(fr["create_time"]) if fr.get("create_time") else None
                view["expected_unfreeze_time"] = (
                    str(fr["auto_unfreeze_time"]) if fr.get("auto_unfreeze_time") else None
                )
        cards.append(view)
    return {"cards": cards, "count": len(cards), "unmasked": unmask}
```

- [ ] **Step 4: 跑测试看绿**

```bash
cd server && uv run pytest tests/agent/test_tool_query_card.py -v
```

Expected: 全 PASS（含新增批查 case + 原有 4 个老 case）。如果老 case 因为 fetch_all 假数据没 target_id 字段而出错，给 fake_db.freezes 的字典补 `"target_id": <id>` 字段。

- [ ] **Step 5: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/agent/tools/query_card.py server/tests/agent/test_tool_query_card.py && \
  git commit -m "perf(query_card): eliminate N+1 with IN batch on freeze_history

原每张冻结/锁定卡查一次 t_tevaupay_bank_card_freeze_history；改成所有 target_id
一次 IN 批查后按 target_id 分组取最新，从 1+N 次降至 2 次（主表 + 冻结表）。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: query_bu_order.py 消除 N+1

**目的**：当前每笔失败订单单查 EXC_SQL；改成所有失败订单的 third_card_id 一次 IN 批查。

**Files:**
- Modify: `server/src/ai_engine/agent/tools/query_bu_order.py`
- Modify: `server/tests/agent/test_tool_query_bu_order.py`

- [ ] **Step 1: 写失败测试**

在 `server/tests/agent/test_tool_query_bu_order.py` 末尾追加（先读现有 fixture 模式再写）：

```bash
cd server && cat tests/agent/test_tool_query_bu_order.py | head -60
```

按现有 _FakeDB 模式扩展（如已有计数器叫 exc_calls 则复用；没有则加）：

```python
class TestBatchExceptionQuery:
    """多笔失败订单共用一次 EXC_SQL 批查。"""

    async def test_three_failed_orders_one_exc_query(self, fake_db) -> None:
        fake_db.orders = [
            {"order_sn": "o1", "trade_order_sn": "to1", "order_type": 18, "status": 4,
             "trade_amount": "100", "fee": "1", "channel_amount": "100", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-01", "end_time": None,
             "remark": None, "third_card_id": "card-A"},
            {"order_sn": "o2", "trade_order_sn": "to2", "order_type": 18, "status": 4,
             "trade_amount": "200", "fee": "1", "channel_amount": "200", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-02", "end_time": None,
             "remark": None, "third_card_id": "card-B"},
            {"order_sn": "o3", "trade_order_sn": "to3", "order_type": 18, "status": 1,
             "trade_amount": "300", "fee": "1", "channel_amount": "300", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-03", "end_time": None,
             "remark": None, "third_card_id": "card-C"},  # status=1 已完成，不查异常
        ]
        fake_db.exceptions = [
            {"card_id": "card-A", "reason": "insufficient funds",
             "error_trans_code": "E01", "trans_type": "PAY", "exception_type": 1,
             "create_time": "2026-01-01"},
            {"card_id": "card-B", "reason": "card frozen",
             "error_trans_code": "E02", "trans_type": "PAY", "exception_type": 1,
             "create_time": "2026-01-02"},
        ]
        out = await qo.run(tenant_id="T1")
        assert fake_db.exc_calls == 1, (
            f"exception table queried {fake_db.exc_calls} times; expected 1 (batched)"
        )
        m = {o["order_sn"]: o for o in out["orders"]}
        assert m["o1"]["failure_reason"]["reason"] == "insufficient funds"
        assert m["o2"]["failure_reason"]["reason"] == "card frozen"
        assert "failure_reason" not in m["o3"]  # 非失败订单不查异常
```

可能需要扩 fake_db 支持 `orders`/`exceptions` 字段与 `exc_calls` 计数；按 SQL 关键字分发到不同列表。

- [ ] **Step 2: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_tool_query_bu_order.py::TestBatchExceptionQuery -v
```

Expected: FAIL — exc_calls=2 或 3。

- [ ] **Step 3: 改 query_bu_order.py 用 IN 批查**

替换 `server/src/ai_engine/agent/tools/query_bu_order.py:21-26 + 72-86 + 89-113`：

```python
# 失败原因批查：所有失败订单的 third_card_id 一次 IN，避免 N+1。
EXC_SQL = """
SELECT card_id, reason, error_trans_code, trans_type, exception_type, create_time
FROM t_nexus_trans_exception
WHERE tenant_id=%s AND card_id IN %s AND del_flag=0
ORDER BY card_id, create_time DESC
"""


def _norm_card_id(v: Any) -> str | None:
    if not v or v in ("", "-"):
        return None
    return str(v)


async def run(tenant_id: str, unmask: bool = False) -> dict[str, Any]:
    """查当前 BU(租户)最近订单（开卡/充值/提现/销卡等及状态）。失败订单的卡级异常一次 IN 批查。"""
    db = get_db("nexus")
    rows = await db.fetch_all(SQL, (tenant_id,), limit=20)

    # 收集失败订单的 third_card_id（去重）
    failed_card_ids = sorted({
        _norm_card_id(r.get("third_card_id"))
        for r in rows if r.get("status") == _FAILED_STATUS
    } - {None})

    exc_by_card: dict[str, dict[str, Any]] = {}
    exc_count_by_card: dict[str, int] = {}
    if failed_card_ids:
        exceptions = await db.fetch_all(
            EXC_SQL,
            (tenant_id, tuple(failed_card_ids)),
            limit=len(failed_card_ids) * 4,
        )
        for ex in exceptions:
            cid = str(ex.get("card_id"))
            exc_count_by_card[cid] = exc_count_by_card.get(cid, 0) + 1
            if cid not in exc_by_card:  # ORDER BY card_id, create_time DESC → 第一条即最新
                exc_by_card[cid] = ex

    orders = []
    for r in rows:
        o: dict[str, Any] = {
            "order_sn": r.get("order_sn"),
            "trade_order_sn": r.get("trade_order_sn"),
            "order_type": label(_ORDER_TYPE, r.get("order_type")),
            "status": label(_STATUS, r.get("status")),
            "trade_amount": str(r["trade_amount"]) if r.get("trade_amount") is not None else None,
            "fee": str(r["fee"]) if r.get("fee") is not None else None,
            "channel_amount": str(r["channel_amount"])
            if r.get("channel_amount") is not None
            else None,
            "currency": r.get("currency"),
            "create_time": str(r["create_time"]) if r.get("create_time") else None,
            "end_time": str(r["end_time"]) if r.get("end_time") else None,
            "remark": r.get("remark"),
        }
        if r.get("status") == _FAILED_STATUS:
            cid = _norm_card_id(r.get("third_card_id"))
            if cid and cid in exc_by_card:
                top = exc_by_card[cid]
                o["failure_reason"] = {
                    "note": "卡级异常线索（按租户+卡号关联，非订单级精确归因）",
                    "reason": top.get("reason"),
                    "error_trans_code": top.get("error_trans_code"),
                    "trans_type": top.get("trans_type"),
                    "exception_count": exc_count_by_card.get(cid, 0),
                }
            else:
                o["failure_reason"] = None
        orders.append(o)
    return {"orders": orders, "count": len(orders)}
```

并移除旧的 `_failure_reason` 函数（已不被引用）。

- [ ] **Step 4: 跑测试看绿**

```bash
cd server && uv run pytest tests/agent/test_tool_query_bu_order.py -v
```

Expected: 全 PASS。

- [ ] **Step 5: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/agent/tools/query_bu_order.py server/tests/agent/test_tool_query_bu_order.py && \
  git commit -m "perf(query_bu_order): eliminate N+1 with IN batch on trans_exception

所有失败订单的 third_card_id 一次 IN 批查异常表，从 1+N 次降到 2 次。
exception_count 由 group-by 后的 count 取代旧的"该卡近期异常数"近似值。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 工具结果 Redis 缓存装饰器

**目的**：同会话多轮重复问"查余额/查卡/查 KYC"时不重复打业务库，30-60s 缓存。

**Files:**
- Create: `server/src/ai_engine/agent/tools/_cache.py`
- Modify: `server/src/ai_engine/agent/tool_router.py`（在 dispatch 内 wrap）
- Modify: `server/src/ai_engine/config.py`（加 cache TTL 配置）
- Create: `server/tests/agent/test_tool_cache.py`

- [ ] **Step 1: config.py 加缓存开关**

在 `server/src/ai_engine/config.py` 适当位置加：

```python
    # 工具结果缓存：同 (tool, normalized_args, subject_id) 在 TTL 内复用 Redis 缓存值。
    # 0 = 关闭。建议生产 30-60s；只对只读 query_* 工具启用。
    tool_cache_ttl_seconds: int = 30
```

- [ ] **Step 2: 写失败测试**

新建 `server/tests/agent/test_tool_cache.py`：

```python
"""工具结果 Redis 缓存：相同 key 在 TTL 内只跑 handler 1 次。

仅 query_* 只读工具启用；create_ticket / mutating 工具不缓存。
"""
import asyncio
import pytest

from ai_engine.agent import tool_router
from ai_engine.agent.tools import base as toolbase
from ai_engine.config import settings


@pytest.fixture(autouse=True)
def _enable_cache(monkeypatch):
    monkeypatch.setattr(settings, "tool_cache_ttl_seconds", 30, raising=False)
    yield


@pytest.fixture
def _counted_tool(monkeypatch):
    """注册 query_dummy 工具，记每次 handler 实际调用次数。"""
    calls = {"n": 0}

    async def _h(user_id: str = "u1") -> dict:
        calls["n"] += 1
        return {"value": calls["n"]}

    toolbase.register(toolbase.Tool(
        name="query_dummy",  # 必须 query_ 前缀才进缓存
        description="d",
        input_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        handler=_h,
        requires_subject_id=True,
        subject_field="user_id",
    ))
    yield calls
    toolbase.REGISTRY.pop("query_dummy", None)


async def test_cache_hits_within_ttl(_counted_tool, monkeypatch):
    # 同 subject_id + 同 args → 2 次 dispatch 只跑 1 次 handler
    r1 = await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U1", conversation_id=1,
    )
    r2 = await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U1", conversation_id=1,
    )
    assert r1["ok"] and r2["ok"]
    assert _counted_tool["n"] == 1, "cache should hide 2nd handler call"
    assert r1["data"] == r2["data"]


async def test_cache_isolated_by_subject(_counted_tool):
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U1", conversation_id=1,
    )
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U2", conversation_id=1,
    )
    assert _counted_tool["n"] == 2, "different subject must not share cache"


async def test_disabled_when_ttl_zero(_counted_tool, monkeypatch):
    monkeypatch.setattr(settings, "tool_cache_ttl_seconds", 0, raising=False)
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U1", conversation_id=1,
    )
    await tool_router.dispatch(
        tool_name="query_dummy", params={}, user_type="c", subject_id="U1", conversation_id=1,
    )
    assert _counted_tool["n"] == 2
```

- [ ] **Step 3: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_tool_cache.py -v
```

Expected: FAIL（calls['n']==2 不等于 1）。

- [ ] **Step 4: 实现缓存层**

新建 `server/src/ai_engine/agent/tools/_cache.py`：

```python
"""工具结果短缓存（spec §11 性能治理）。

仅对 query_* 只读工具生效；create_ticket / mutating 工具一律穿透。
Redis 不可达或未配置时直接穿透，不影响业务（fail-open）。
缓存 key = sha256(tool + sorted_args + subject_id)；value = json，TTL = settings.tool_cache_ttl_seconds。
"""
import hashlib
import json
import logging
from typing import Any

from ai_engine.config import settings
from ai_engine.governance import rate_limit  # 复用其 redis client（已有）

logger = logging.getLogger(__name__)


def _is_cacheable(tool_name: str) -> bool:
    """只对查询类工具启用缓存。"""
    return tool_name.startswith("query_")


def _key(tool_name: str, params: dict[str, Any], subject_id: str) -> str:
    canon = json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)
    h = hashlib.sha256(f"{tool_name}|{subject_id}|{canon}".encode()).hexdigest()[:24]
    return f"cs:tool:{tool_name}:{h}"


async def get(tool_name: str, params: dict[str, Any], subject_id: str) -> dict[str, Any] | None:
    if settings.tool_cache_ttl_seconds <= 0 or not _is_cacheable(tool_name):
        return None
    redis = await rate_limit._get_redis()  # noqa: SLF001  — 复用现有 client
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


async def set_(tool_name: str, params: dict[str, Any], subject_id: str, result: dict[str, Any]) -> None:
    if settings.tool_cache_ttl_seconds <= 0 or not _is_cacheable(tool_name):
        return
    redis = await rate_limit._get_redis()  # noqa: SLF001
    if redis is None:
        return
    if not result.get("ok"):
        return  # 失败结果不缓存（让下次重试）
    try:
        await redis.set(
            _key(tool_name, params, subject_id),
            json.dumps(result, ensure_ascii=False, default=str),
            ex=settings.tool_cache_ttl_seconds,
        )
    except Exception:
        logger.warning("tool cache set failed", exc_info=True)
```

注：上面对 `rate_limit._get_redis()` 的复用，先确认 rate_limit.py 暴露了 redis client。若没有该函数，需要：

```bash
cd server && grep -n "redis\|Redis" src/ai_engine/governance/rate_limit.py | head -20
```

如果 rate_limit 没暴露 redis client：复用 redis_url 自建一个 `_redis: redis.asyncio.Redis | None`，按 settings.redis_url 懒加载，None 时穿透。

替代实现（独立 redis client）：

```python
# _cache.py 顶部
import os
try:
    from redis.asyncio import Redis
except ImportError:
    Redis = None  # 测试或未装 redis 时 fail-open

_redis_client: Any = None
async def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.redis_url or Redis is None:
        return None
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client
```

然后 `get` / `set_` 里改用本地 `_get_redis()`。

- [ ] **Step 5: 在 tool_router.dispatch 里 wrap 缓存**

读 `server/src/ai_engine/agent/tool_router.py` 找 `dispatch` 函数 entry：

```bash
cd server && grep -n "^async def dispatch\|^def dispatch" src/ai_engine/agent/tool_router.py
```

在 dispatch 真正调用 handler 之前先查缓存，handler 返回成功后写缓存。dispatch 体内（找到 "r = await tool.handler(**params)" 或类似的位置）替换为：

```python
from ai_engine.agent.tools import _cache as tool_cache

# ... dispatch 内：
# 先查缓存（仅 query_*，subject_id 注入后的 params 已 canonical）
cached = await tool_cache.get(tool_name, params, subject_id)
if cached is not None:
    return cached

result = await tool.handler(**params)  # 原有调用，保留
wrapped = {"ok": True, "data": result}  # 按现有 dispatch 包装方式调整
# ... 现有错误兜底 / payload 包装 ...
await tool_cache.set_(tool_name, params, subject_id, wrapped)
return wrapped
```

具体行号需要在执行时按 dispatch 实际结构调整——大体逻辑：handler 调用前 try-cache，handler 调用后 write-cache。

- [ ] **Step 6: 跑测试看绿**

```bash
cd server && uv run pytest tests/agent/test_tool_cache.py -v
```

Expected: 3 个 case 全 PASS。如果 redis 未跑或 redis-py 未装，测试需要 fakeredis fixture——若已有 redis fixture 复用之；否则用 fakeredis-py：

```bash
cd server && uv add --dev fakeredis
```

然后测试 fixture 用 `fakeredis.aioredis.FakeRedis()` 替换 `_get_redis()` 返回值（monkeypatch）。

- [ ] **Step 7: 跑全部 tool 相关测试**

```bash
cd server && uv run pytest tests/agent/test_tool_query_card.py tests/agent/test_tool_query_bu_order.py \
  tests/agent/test_runtime_tool_loop.py tests/agent/test_tool_cache.py -v
```

Expected: 全 PASS。

- [ ] **Step 8: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/agent/tools/_cache.py server/src/ai_engine/agent/tool_router.py \
          server/src/ai_engine/config.py server/tests/agent/test_tool_cache.py && \
  git commit -m "feat(tools): redis short-cache for query_* read-only tools

dispatch 入口对 tool_name 前缀 query_ 的工具做 sha256(tool|subject|args) 缓存，
TTL settings.tool_cache_ttl_seconds（默认 30s）。create_ticket / mutating 工具
穿透；Redis 不可达 fail-open。同会话多轮重复查同用户数据不再每轮打业务库。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: topic_classifier 对已绑定身份用户跳过

**目的**：已认证 C 端用户 / B 端 tenant 不再每条消息跑 Haiku 二层分类，省 200-400ms/轮。游客（user_type==g）仍走分类（边界更危险）。

**Files:**
- Modify: `server/src/ai_engine/config.py`
- Modify: `server/src/ai_engine/agent/runtime.py:339`（classifier 入口判断）
- Modify: `server/tests/agent/test_runtime_classifier_gate.py`

- [ ] **Step 1: config.py 加白名单开关**

```python
    # 已绑定身份（C 端 user / B 端 tenant）跳过 Haiku 二层分类；游客仍跑。省一次 LLM 跳跃。
    topic_classifier_skip_authed: bool = True
```

- [ ] **Step 2: 写失败测试**

在 `server/tests/agent/test_runtime_classifier_gate.py` 末尾追加（先看现有结构）：

```bash
cd server && cat tests/agent/test_runtime_classifier_gate.py | head -50
```

按现有结构追加：

```python
class TestSkipForAuthed:
    """topic_classifier_enabled + skip_authed=True 时，C 端已绑定用户跳过分类。"""

    async def test_authed_c_skips_haiku(self, monkeypatch, seeded_db, fake_stream, make_resp):
        from ai_engine.config import settings
        monkeypatch.setattr(settings, "topic_classifier_enabled", True, raising=False)
        monkeypatch.setattr(settings, "topic_classifier_skip_authed", True, raising=False)

        called = {"n": 0}

        async def _classify(_m):
            called["n"] += 1
            return "yes"

        from ai_engine.agent import topic_classifier as tc
        monkeypatch.setattr(tc, "classify", _classify)

        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream([
            make_resp(text="draft"), make_resp(text="ok"),
        ]))
        conv = await create_conversation("c", "U_AUTH")
        _ = [e async for e in rt.run_turn(
            conversation_id=conv, user_type="c", subject_id="U_AUTH",
            user_message="为什么我的卡被冻结了",
        )]
        assert called["n"] == 0, "authed C user should skip topic classifier"

    async def test_guest_still_classified(self, monkeypatch, seeded_db, fake_stream, make_resp):
        from ai_engine.config import settings
        monkeypatch.setattr(settings, "topic_classifier_enabled", True, raising=False)
        monkeypatch.setattr(settings, "topic_classifier_skip_authed", True, raising=False)

        called = {"n": 0}
        async def _classify(_m):
            called["n"] += 1
            return "yes"
        from ai_engine.agent import topic_classifier as tc
        monkeypatch.setattr(tc, "classify", _classify)

        monkeypatch.setattr(_ac._client.messages, "stream", fake_stream([
            make_resp(text="draft"), make_resp(text="ok"),
        ]))
        conv = await create_conversation("g", "anon")
        _ = [e async for e in rt.run_turn(
            conversation_id=conv, user_type="g", subject_id="anon",
            user_message="hi",
        )]
        assert called["n"] == 1, "guest must still go through topic classifier"
```

- [ ] **Step 3: 跑测试看红**

```bash
cd server && uv run pytest tests/agent/test_runtime_classifier_gate.py::TestSkipForAuthed -v
```

Expected: FAIL — called['n']==1 for authed case。

- [ ] **Step 4: runtime.py 改 classifier 入口判断**

在 `server/src/ai_engine/agent/runtime.py:339` 区域：

```python
    # spec §6.4 第二层：haiku 前置话题分类（按需开启）。判定一律落库 + 计数。
    # 纯图片消息（文本为空）无可分类文本，跳过分类视为放行，交给主模型 vision 判断。
    # 已绑定身份用户（C 端 user / B 端 tenant）跳过：游客仍跑（边界更危险）。
    _is_guest = (user_type == "g")
    _should_classify = (
        settings.topic_classifier_enabled
        and user_message.strip()
        and (not settings.topic_classifier_skip_authed or _is_guest)
    )
    if _should_classify:
        verdict = await topic_classifier.classify(user_message)
        await set_turn_verdict(turn_id, verdict)
        metrics.topic_verdict_total.labels(verdict=verdict).inc()
        if verdict == "no":
            # ... 原 refusal 代码保留
```

注：`USER_TYPE_GUEST = "g"` 见 `ai_engine.auth.bu_session`，可直接比较字面 "g" 或 import 常量。

- [ ] **Step 5: 跑测试看绿**

```bash
cd server && uv run pytest tests/agent/test_runtime_classifier_gate.py -v
```

Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/src/ai_engine/agent/runtime.py server/src/ai_engine/config.py \
          server/tests/agent/test_runtime_classifier_gate.py && \
  git commit -m "perf(classifier): skip haiku 2nd-layer for authed users

C 端已登录 / B 端 tenant 默认跳过 topic_classifier 二层分类，省 1 次 Haiku 调用
（200-400ms/轮）。游客 user_type=='g' 仍跑（边界更脆弱）。topic_classifier_skip_authed
开关可一键回退。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Dockerfile 多 worker + 暴露 sem 配置

**目的**：单进程 uvicorn 利用不上多核；改 workers + 暴露 env 让运维可调 LLM_MAX_CONCURRENCY / TOOL_CACHE_TTL。

**Files:**
- Modify: `server/Dockerfile`
- Modify: `server/docker-compose.yml`（项目根 `docker-compose.yml`）或 README 注明 env

- [ ] **Step 1: 改 Dockerfile**

将 `server/Dockerfile:18` 那行 CMD 改为：

```dockerfile
# UVICORN_WORKERS env 可在 compose / k8s 注入；默认 2，按容器 CPU 配（一般 = nproc 或 2×nproc+1）
# 多 worker → 须把进程内状态（_cancel_signals dict、tool_router cache dict）外移 Redis
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "exec uvicorn ai_engine.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
```

- [ ] **Step 2: docker-compose.yml 暴露 env**

读取并更新（位置：项目根 `docker-compose.yml`）：

```bash
cat docker-compose.yml
```

在 `api` 服务的 environment 段（已有 `ANTHROPIC_API_KEY` 那块）追加：

```yaml
      UVICORN_WORKERS: "2"
      LLM_MAX_CONCURRENCY: "20"
      LLM_ACQUIRE_TIMEOUT_SECONDS: "0.5"
      TOOL_CACHE_TTL_SECONDS: "30"
      TOPIC_CLASSIFIER_SKIP_AUTHED: "true"
```

- [ ] **Step 3: 关键风险——进程内状态确认**

检查多 worker 不会破的进程内状态：

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine/server && \
  grep -rn "^_[a-z_]*:.*dict\|^_[a-z_]*: dict\|^_[a-z_]*: dict\[" src/ai_engine/ | head -30
```

至少要检查的状态：
- `chat.py:_cancel_signals` — 进程间不共享，但 cancel DELETE 也走同一进程的可能性 < 1/N。需要把 cancel 信号迁 Redis pub/sub：本计划暂不实施（注解，给后续任务）
- `tool_router.py:32` userCode→user_id 内存映射 — 每 worker 各自一份 cache 是 OK 的（5min TTL，重复就重新查一次），不强制要迁
- `topic_classifier` / `prompt registry` — 无写状态，纯函数

把已知的"多 worker 不一致"风险写进 plan 提示——本任务不修复，留作下一阶段；主要风险是 cancel DELETE 偶尔打不到正在 stream 的 worker，但 Task 2 的 `_watch_disconnect` 已经能用 client TCP 断开兜底，所以可接受。

- [ ] **Step 4: 重新构建确认启动正常**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && docker compose up -d --build api && docker compose logs --tail=20 api
```

Expected: 看到 `Started server process` 出现 2 次（每 worker 一条），无报错。

- [ ] **Step 5: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && \
  git add server/Dockerfile docker-compose.yml && \
  git commit -m "ops(deploy): multi-worker uvicorn + LLM/cache env exposure

UVICORN_WORKERS=2 默认；env 暴露 LLM_MAX_CONCURRENCY / LLM_ACQUIRE_TIMEOUT_SECONDS
/ TOOL_CACHE_TTL_SECONDS / TOPIC_CLASSIFIER_SKIP_AUTHED 让运维按容量调整。
注：cancel DELETE 跨 worker 偶达不到，靠 _watch_disconnect 的 TCP 断开兜底。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## 全量验证

完成全部 8 个任务后跑一次集合：

- [ ] **Step 1: 跑整套单元 + 集成测试**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine/server && uv run pytest -x --timeout=60
```

Expected: 全 PASS。

- [ ] **Step 2: 跑 type check**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine/server && uv run mypy src/ai_engine || true
```

记录 mypy 增量错误（非阻塞）。

- [ ] **Step 3: 重启确认**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine && docker compose up -d --build api
docker compose logs --tail=50 api
```

Expected: 多 worker 启动、无 import 错误。

- [ ] **Step 4: 端到端 smoke**

向 `/api/v1/chat` 发一条测试消息，确认：
- SSE 流正常输出
- 中断（断开 webview）后 anthropic 不再继续流（看日志/Anthropic dashboard）
- 多个 query 工具一轮调用时间显著缩短

---

## 自检（Self-Review）

**Spec 覆盖：**
- ✅ #1 并发承载 → Task 1（Semaphore）+ Task 8（多 worker）
- ✅ #2 SSE 中断 → Task 1（async with stream）+ Task 2（disconnect watcher）
- ✅ #3 查库慢 → Task 3（并发 gather）+ Task 4/5（N+1 修）+ Task 6（缓存）
- ✅ #4 节点架构 → Task 7（已认证用户跳分类）；架构主体保留不动（已合理）
- ❌ #1 全局指标看板 / 灰度看板：本 plan 仅加 inflight gauge + busy counter，看板搭建留运维
- ❌ #2.5 前端心跳：脱出后端 plan 范围
- ❌ #3.4 read replica / EXPLAIN 审计：DBA 协作，留下一 plan
- ❌ #4.B 灰度看板 / #4.C eval 集：数据 + 标注资源，留产品/运营

**类型一致性：** Semaphore / SystemBusy / `_run_tools` 签名前后一致。

**留作下一阶段：**
1. 前端 H5 心跳回信 + UI 显示 "系统繁忙稍后重试"（捕获 SystemBusy 错误码）
2. Cancel DELETE 跨 worker 的 Redis pub/sub 传播
3. 业务库索引审计 + read replica 切换
4. 灰度对照 / eval 评测集（人工标注启动）
