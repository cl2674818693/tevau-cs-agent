# 可靠性加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（本会话内联执行）。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐对话引擎的「留痕缺口」与「中断兜底」两类能力——让"用户问了什么 / AI 差了什么"可量化，让"超时 / 中断 / 重复请求"有确定的兜底。

**Architecture:** 后端 FastAPI + SQLAlchemy Core(双方言 PG/SQLite) + alembic 迁移。核心思路是把「一次 AI 回合(turn)」绑定到该回合的 user 消息行上，用其 `status` 字段(processing→done/failed)作为回合状态机，并以此承载幂等(client_message_id)、僵尸清理、失败兜底。话题判定与 👍/👎 反馈各自落库 + Prometheus 计数，知识缺口报表做聚合查询。前端补 client_message_id 与反馈按钮。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core async / alembic / prometheus_client / pytest；前端 React + TS + vitest。

---

## File Structure

新增/修改：

- `server/src/ai_engine/persistence/schema.py` — messages 加列 + 新表 message_feedback
- `server/migrations/versions/<new>_reliability.py` — alembic 迁移(新建)
- `server/src/ai_engine/persistence/conversations.py` — turn 生命周期 / 幂等 / verdict / 僵尸清理 DAO
- `server/src/ai_engine/persistence/feedback.py` — 反馈 DAO(新建)
- `server/src/ai_engine/persistence/insights.py` — 知识缺口聚合查询(新建)
- `server/src/ai_engine/observability/metrics.py` — 新计数器
- `server/src/ai_engine/agent/runtime.py` — fail-soft + turn 状态 + verdict 记录
- `server/src/ai_engine/api/chat.py` — 幂等替身重放 + 失败兜底联动
- `server/src/ai_engine/api/feedback.py` — 反馈端点(新建)
- `server/src/ai_engine/api/insights.py` — 知识缺口端点(新建)
- `server/src/ai_engine/persistence/maintenance.py` — 僵尸 turn 清理(新建)
- `server/src/ai_engine/main.py` — 注册新路由 + 启动后台清理任务
- `server/src/ai_engine/config.py` — 新增清理间隔/阈值配置
- `web/src/api/chat.ts` / `web/src/hooks/useChat.ts` — client_message_id
- `web/src/api/chat.ts` / `web/src/components/MessageBubble.tsx`(或 ChatExtras) — 👍/👎

---

## Task 1: Schema 加列 + 反馈表 + alembic 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py:49-58`（messages）
- Modify: `server/src/ai_engine/persistence/schema.py`（文件末尾追加 message_feedback）
- Create: `server/migrations/versions/<rev>_reliability.py`
- Test: `server/tests/test_alembic_migrations.py`（已有 parity 测试自动覆盖新表/新列存在性）

设计：
- `messages` 增列：
  - `status` String(16) server_default `'done'`（user 行：processing→done/failed；其余行恒 done）
  - `error_code` String(32) nullable（status=failed 时写入）
  - `client_message_id` String(64) nullable（幂等键，仅 user 行写）
  - `topic_verdict` String(16) nullable（仅 user 行写：yes/no/uncertain）
- 新表 `message_feedback`：id, conversation_id, message_id(FK messages.id), rating String(8)('up'/'down'), reason Text nullable, subject_id, user_type, created_at。CheckConstraint rating IN ('up','down')。索引 idx_feedback_conv。
- 新索引 `idx_msg_client` on messages(conversation_id, client_message_id)。

- [ ] **Step 1: 改 schema.py messages 表 + 加 message_feedback 表 + 索引**

messages Table 改为：
```python
messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, ForeignKey("conversations.id"), nullable=False),
    Column("role", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("sender_staff_id", String(64)),
    Column("status", String(16), nullable=False, server_default="done"),
    Column("error_code", String(32)),
    Column("client_message_id", String(64)),
    Column("topic_verdict", String(16)),
    Column("created_at", String(32), nullable=False),
)
Index("idx_msg_client", messages.c.conversation_id, messages.c.client_message_id)
```
文件末尾追加：
```python
message_feedback = Table(
    "message_feedback",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("message_id", Integer, ForeignKey("messages.id"), nullable=False),
    Column("rating", String(8), nullable=False),
    Column("reason", Text),
    Column("subject_id", String(128), nullable=False),
    Column("user_type", String(8), nullable=False),
    Column("created_at", String(32), nullable=False),
    CheckConstraint("rating IN ('up','down')", name="ck_feedback_rating"),
)
Index("idx_feedback_conv", message_feedback.c.conversation_id)
```

- [ ] **Step 2: 生成 alembic 迁移**

Run: `cd server && .venv/bin/alembic revision --autogenerate -m "reliability: msg status/idempotency/verdict + feedback"`
Expected: 在 migrations/versions 下生成新文件，含 add_column(messages,...) ×4、create_table(message_feedback)、create_index ×2。
人工核对：确认 4 个 add_column 有 server_default（status）/ nullable=True（其余），下游不报 NOT NULL。

- [ ] **Step 3: 跑迁移 parity 测试**

Run: `cd server && .venv/bin/pytest tests/test_alembic_migrations.py -v`
Expected: PASS（expected 表集合现在包含 message_feedback；upgrade head 建出全部表）。

- [ ] **Step 4: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions
git commit -m "feat(db): messages 加 status/error_code/client_message_id/topic_verdict + message_feedback 表"
```

---

## Task 2: turn 生命周期 / 幂等 / verdict DAO

**Files:**
- Modify: `server/src/ai_engine/persistence/conversations.py`
- Test: `server/tests/test_turn_lifecycle.py`（新建）

新增函数（conversations.py）：
```python
async def append_user_turn(
    conv_id: int, content: str, client_message_id: str | None
) -> int:
    """开启一个 AI 回合：user 消息入库，status=processing。返回 message_id(turn_id)。"""
    return await db.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, status, client_message_id, created_at) "
        "VALUES (:cid, 'user', :content, 'processing', :cmid, :now) RETURNING id",
        {"cid": conv_id, "content": content, "cmid": client_message_id, "now": now_str()},
    )


async def finalize_turn(turn_id: int, status: str, error_code: str | None = None) -> None:
    """收尾回合：status=done/failed。"""
    await db.execute(
        "UPDATE messages SET status=:st, error_code=:ec WHERE id=:id",
        {"st": status, "ec": error_code, "id": turn_id},
    )


async def set_turn_verdict(turn_id: int, verdict: str) -> None:
    await db.execute(
        "UPDATE messages SET topic_verdict=:v WHERE id=:id",
        {"v": verdict, "id": turn_id},
    )


async def find_completed_turn(conv_id: int, client_message_id: str) -> dict[str, object] | None:
    """幂等：按 client_message_id 找已完成(status=done)的 user 回合行。"""
    return await db.fetch_one(
        "SELECT id, content FROM messages WHERE conversation_id=:cid "
        "AND client_message_id=:cmid AND role='user' AND status='done' "
        "ORDER BY id DESC LIMIT 1",
        {"cid": conv_id, "cmid": client_message_id},
    )


async def get_turn_assistant_texts(conv_id: int, turn_id: int) -> list[str]:
    """取某回合 user 行(turn_id)之后、下一条 user 行之前的所有 assistant 文本(已是纯文本/JSON)。"""
    rows = await db.fetch_all(
        "SELECT id, role, content FROM messages WHERE conversation_id=:cid AND id>:tid "
        "ORDER BY id",
        {"cid": conv_id, "tid": turn_id},
    )
    out: list[str] = []
    for r in rows:
        if r["role"] == "user":
            break
        if r["role"] == "assistant":
            out.append(str(r["content"]))
    return out
```
注：`get_turn_assistant_texts` 返回的 assistant content 是 `json.dumps([{type:text,...}])` 格式；重放方负责还原（复用 runtime._history_text）。

- [ ] **Step 1: 写失败测试 test_turn_lifecycle.py**

```python
async def test_turn_processing_then_done(seeded_db):
    from ai_engine.persistence import conversations as c
    tid = await c.append_user_turn(1, "hi", "cmid-1")
    rows = await c.list_messages(1)
    assert any(r["id"] == tid and r["status"] == "processing" for r in rows)
    await c.finalize_turn(tid, "done")
    assert await c.find_completed_turn(1, "cmid-1") is not None


async def test_find_completed_turn_ignores_processing(seeded_db):
    from ai_engine.persistence import conversations as c
    await c.append_user_turn(1, "hi", "cmid-2")  # 留在 processing
    assert await c.find_completed_turn(1, "cmid-2") is None


async def test_turn_verdict_and_assistant_texts(seeded_db):
    from ai_engine.persistence import conversations as c
    tid = await c.append_user_turn(1, "q", "cmid-3")
    await c.set_turn_verdict(tid, "no")
    await c.append_message(1, "assistant", "答复A")
    await c.append_message(1, "assistant", "答复B")
    txts = await c.get_turn_assistant_texts(1, tid)
    assert txts == ["答复A", "答复B"]
    rows = await c.list_messages(1)
    assert any(r["id"] == tid and r["topic_verdict"] == "no" for r in rows)
```
注：`list_messages` 当前 SELECT 不含 status/topic_verdict，需在 Step 3 扩展其 SELECT 列。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && .venv/bin/pytest tests/test_turn_lifecycle.py -v`
Expected: FAIL（函数不存在）。

- [ ] **Step 3: 实现 DAO + 扩展 list_messages SELECT**

把上面 4 个函数加进 conversations.py。并把 `list_messages` 的 SELECT 改为：
```python
"SELECT id, role, content, sender_staff_id, status, error_code, "
"client_message_id, topic_verdict, created_at FROM messages "
"WHERE conversation_id=:id ORDER BY id"
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd server && .venv/bin/pytest tests/test_turn_lifecycle.py tests/test_history_replay.py tests/test_conversations_api.py -v`
Expected: PASS（确认扩展 SELECT 没破坏历史回放）。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/conversations.py server/tests/test_turn_lifecycle.py
git commit -m "feat(db): turn 生命周期/幂等/verdict DAO + list_messages 暴露新列"
```

---

## Task 3: 新增 Prometheus 计数器

**Files:**
- Modify: `server/src/ai_engine/observability/metrics.py`
- Test: `server/tests/test_metrics.py`（追加断言计数器存在）

- [ ] **Step 1: 加计数器**

文件末尾追加：
```python
# 留痕：话题判定 / 反馈 / 失败兜底 / 僵尸清理
topic_verdict_total = Counter("ai_engine_topic_verdict_total", "话题分类判定", ["verdict"])
message_feedback_total = Counter("ai_engine_message_feedback_total", "消息反馈", ["rating"])
llm_turn_failures_total = Counter("ai_engine_llm_turn_failures_total", "回合内 LLM 失败兜底次数")
stale_turns_reclaimed_total = Counter(
    "ai_engine_stale_turns_reclaimed_total", "超时僵尸回合被标记 failed 的数量"
)
```

- [ ] **Step 2: 测试 + 通过**

在 test_metrics.py 追加：
```python
def test_reliability_counters_exist():
    from ai_engine.observability import metrics
    assert metrics.topic_verdict_total
    assert metrics.message_feedback_total
    assert metrics.llm_turn_failures_total
    assert metrics.stale_turns_reclaimed_total
```
Run: `cd server && .venv/bin/pytest tests/test_metrics.py -v` → PASS

- [ ] **Step 3: Commit**

```bash
git add server/src/ai_engine/observability/metrics.py server/tests/test_metrics.py
git commit -m "feat(obs): 加 verdict/feedback/失败/僵尸清理 计数器"
```

---

## Task 4: runtime fail-soft + turn 状态机 + verdict 记录

**Files:**
- Modify: `server/src/ai_engine/agent/runtime.py:164-211`
- Test: `server/tests/test_runtime_failsoft.py`（新建）

设计要点（run_turn 重构）：
1. 用 `append_user_turn(...)` 替换原 line 187 的 `append_message(... role="user" ...)`，拿到 `turn_id`；签名加 `client_message_id: str | None = None`。
2. 原 line 186 的 in-memory `messages.append({"role":"user",...})` 保留（_load_history 在 184 已先跑，不含本回合）。
3. topic 分类：classify 后 `await set_turn_verdict(turn_id, verdict)` 并 `metrics.topic_verdict_total.labels(verdict=verdict).inc()`。verdict=="no" 分支末尾 `await finalize_turn(turn_id, "done")` 再 return。
4. 把 `_agent_loop` 调用包进 try/except：
   - 正常结束 → `await finalize_turn(turn_id, "done")`
   - except Exception → `metrics.llm_turn_failures_total.inc()`；`await finalize_turn(turn_id, "failed", "INTERNAL_ERROR")`；`yield {"type": "error", "code": "INTERNAL_ERROR", "text": _FAILSOFT_TEXT}`；不 re-raise（fail-soft）。
5. 新增模块常量 `_FAILSOFT_TEXT = "抱歉，我这边暂时出了点问题，请重发一次，或点'转人工'。"`

run_turn 改写后骨架：
```python
async def run_turn(
    *, conversation_id: int, user_type: str, subject_id: str,
    user_message: str, model: str | None = None, client_message_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    prompt_version = pick_version(subject_id)
    model = model or model_for(prompt_version) or settings.default_model
    system_blocks = build_system_blocks(user_type=user_type, version=prompt_version)
    tools = base.all_definitions()

    conversation_id, compact_event, messages = await _maybe_compact(conversation_id)
    if compact_event:
        yield compact_event
    else:
        messages = await _load_history(conversation_id)

    messages.append({"role": "user", "content": user_message})
    turn_id = await append_user_turn(conversation_id, user_message, client_message_id)

    if settings.topic_classifier_enabled:
        verdict = await topic_classifier.classify(user_message)
        await set_turn_verdict(turn_id, verdict)
        metrics.topic_verdict_total.labels(verdict=verdict).inc()
        if verdict == "no":
            refusal = topic_classifier.refusal_text(user_type)
            await append_message(conversation_id, role="assistant", content=refusal)
            await finalize_turn(turn_id, "done")
            yield {"type": "text", "text": refusal}
            return
        if verdict == "uncertain":
            system_blocks = [*system_blocks, {"type": "text", "text": topic_classifier.UNCERTAIN_HINT}]

    guard = CostGuard(max_depth=settings.max_tool_depth, max_result_bytes=settings.max_tool_result_bytes)
    try:
        with metrics.active_conversations.track_inprogress():
            async for ev in _agent_loop(
                system_blocks, tools, model, messages, guard, user_type, subject_id, conversation_id
            ):
                yield ev
        await finalize_turn(turn_id, "done")
    except Exception:
        logger.exception("agent turn failed (conversation_id=%s)", conversation_id)
        metrics.llm_turn_failures_total.inc()
        await finalize_turn(turn_id, "failed", "INTERNAL_ERROR")
        yield {"type": "error", "code": "INTERNAL_ERROR", "text": _FAILSOFT_TEXT}
```
新增 import：`from ai_engine.persistence.conversations import append_message, append_user_turn, finalize_turn, list_messages, set_turn_verdict` + `import logging` + `logger = logging.getLogger(__name__)`。

注意：`collect_full_response`(ai_draft 路径)也走 run_turn，新 except 分支会 yield type=error；它只收集 type=="text"，error 事件被忽略——可接受（草稿为空，客服侧自然会看到）。

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import AsyncMock, MagicMock


async def test_run_turn_failsoft_on_llm_exception(seeded_db, monkeypatch):
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence import conversations as c

    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(ac, "_client", fake)

    evs = [ev async for ev in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="S1",
        user_message="q", client_message_id="cm-fail")]

    assert any(e.get("type") == "error" for e in evs)  # 兜底文案而非裸抛
    rows = await c.list_messages(1)
    turn = [r for r in rows if r["role"] == "user" and r["client_message_id"] == "cm-fail"][0]
    assert turn["status"] == "failed"
    assert turn["error_code"] == "INTERNAL_ERROR"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && .venv/bin/pytest tests/test_runtime_failsoft.py -v`
Expected: FAIL（当前裸抛 RuntimeError）。

- [ ] **Step 3: 重构 run_turn（按上面骨架）**

- [ ] **Step 4: 跑测试 + 回归**

Run: `cd server && .venv/bin/pytest tests/test_runtime_failsoft.py tests/test_agent_runtime.py tests/test_topic_classifier.py tests/test_self_check.py tests/test_ai_draft.py -v`
Expected: PASS。若 test_topic_classifier 的 `test_run_turn_no_verdict_short_circuits` 因 verdict 记录新增 DB 写而受影响——它用 seeded_db，应正常。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/agent/runtime.py server/tests/test_runtime_failsoft.py
git commit -m "feat(agent): run_turn fail-soft 兜底 + turn 状态机(processing/done/failed) + verdict 落库"
```

---

## Task 5: chat.py 幂等重放 + 失败事件映射

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`
- Test: `server/tests/test_chat_idempotency.py`（新建）

设计：
1. `chat()` 加 query 参数 `client_message_id: str | None = Query(default=None)`。
2. 在进入 agent 前（mode 检查之后、ai_draft 之前合适位置——放在 message_start 之前），若 `client_message_id` 非空：`prev = await conv_dao.find_completed_turn(conversation_id, client_message_id)`；若命中 → 重放该回合 assistant 文本（用 runtime._history_text 还原），逐段 yield content_block_delta，再 message_stop(stop_reason="replayed")，return。不再调 LLM。
3. 把 `client_message_id` 透传给 `runtime.run_turn(...)`。
4. `_map_runtime_event` 增加对 `type=="error"` 的映射 → `se.error_event(ev["code"], ev["text"])`，让 runtime fail-soft 文案能到前端。

新增 import：`from ai_engine.agent.runtime import _history_text`（或在 chat.py 内联还原逻辑，避免依赖私有函数——这里复用，标注）。

幂等重放片段（放在 message_start yield 之前）：
```python
if client_message_id:
    prev = await conv_dao.find_completed_turn(conversation_id, client_message_id)
    if prev:
        texts = await conv_dao.get_turn_assistant_texts(conversation_id, int(prev["id"]))
        yield se.sse_payload(se.EVENT_MESSAGE_START, {"message_id": secrets.token_hex(6)})
        for raw in texts:
            yield se.sse_payload(
                se.EVENT_CONTENT_BLOCK_DELTA,
                {"index": 0, "delta": {"type": "text_delta", "text": runtime._history_text("assistant", raw)}},
            )
        yield se.sse_payload(se.EVENT_MESSAGE_STOP, {"stop_reason": "replayed"})
        return
```
`_map_runtime_event` 追加：
```python
if t == "error":
    return se.error_event(ev.get("code", "INTERNAL_ERROR"), ev.get("text", ""))
```
`run_turn` 调用追加 `client_message_id=client_message_id`。

- [ ] **Step 1: 写失败测试**

```python
from httpx import ASGITransport, AsyncClient


async def test_chat_replays_on_duplicate_client_message_id(seeded_db, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    calls = {"n": 0}

    async def fake_run_turn(**kwargs):
        calls["n"] += 1
        from ai_engine.persistence.conversations import append_user_turn, append_message, finalize_turn
        tid = await append_user_turn(kwargs["conversation_id"], kwargs["user_message"], kwargs.get("client_message_id"))
        import json
        await append_message(kwargs["conversation_id"], "assistant", json.dumps([{"type": "text", "text": "原始答复"}], ensure_ascii=False))
        await finalize_turn(tid, "done")
        yield {"type": "text", "text": "原始答复"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"})
        cid = init.json()["conversation_id"]
        url = f"/api/v1/chat?conversation_id={cid}&message=hi&client_message_id=cm-dup"
        async with client.stream("GET", url, headers={"X-BU-ID": "BU00243780"}) as r1:
            _ = [l async for l in r1.aiter_lines()]
        async with client.stream("GET", url, headers={"X-BU-ID": "BU00243780"}) as r2:
            lines2 = [l async for l in r2.aiter_lines()]

    assert calls["n"] == 1  # 第二次未再调 run_turn
    assert any("replayed" in l for l in lines2)
    assert any("原始答复" in l for l in lines2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && .venv/bin/pytest tests/test_chat_idempotency.py -v` → FAIL

- [ ] **Step 3: 实现 chat.py 改动**

- [ ] **Step 4: 跑测试 + 回归**

Run: `cd server && .venv/bin/pytest tests/test_chat_idempotency.py tests/test_chat_api.py tests/test_chat_human_mode.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/api/chat.py server/tests/test_chat_idempotency.py
git commit -m "feat(chat): client_message_id 幂等重放 + 失败事件映射到前端"
```

---

## Task 6: 反馈 DAO + 端点

**Files:**
- Create: `server/src/ai_engine/persistence/feedback.py`
- Create: `server/src/ai_engine/api/feedback.py`
- Modify: `server/src/ai_engine/main.py`（注册路由）
- Test: `server/tests/test_feedback.py`（新建）

feedback.py：
```python
from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def add_feedback(
    conversation_id: int, message_id: int, rating: str, reason: str | None,
    subject_id: str, user_type: str,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO message_feedback"
        "(conversation_id, message_id, rating, reason, subject_id, user_type, created_at) "
        "VALUES (:cid, :mid, :r, :reason, :sid, :ut, :now) RETURNING id",
        {"cid": conversation_id, "mid": message_id, "r": rating, "reason": reason,
         "sid": subject_id, "ut": user_type, "now": now_str()},
    )
```

api/feedback.py（复用 chat 的归属校验逻辑）：
```python
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ai_engine.api.chat import _authorize_conversation
from ai_engine.observability import metrics
from ai_engine.persistence import feedback as fb_dao

router = APIRouter()


class FeedbackIn(BaseModel):
    message_id: int
    rating: str  # "up" | "down"
    reason: str | None = None


@router.post("/api/v1/conversations/{conv_id}/feedback")
async def submit_feedback(conv_id: int, body: FeedbackIn, request: Request) -> dict[str, Any]:
    if body.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be up/down")
    user_type, subject_id = await _authorize_conversation(request, conv_id)
    await fb_dao.add_feedback(conv_id, body.message_id, body.rating, body.reason, subject_id, user_type)
    metrics.message_feedback_total.labels(rating=body.rating).inc()
    return {"ok": True}
```
main.py：`from ai_engine.api.feedback import router as feedback_router` + `app.include_router(feedback_router)`。

- [ ] **Step 1: 写失败测试**

```python
from httpx import ASGITransport, AsyncClient
_H = {"X-BU-ID": "BU00243780"}


async def test_submit_feedback_persists_and_counts(seeded_db):
    from ai_engine import main as main_mod
    from ai_engine.persistence import db
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        r = await client.post(f"/api/v1/conversations/{cid}/feedback",
                              json={"message_id": 1, "rating": "down", "reason": "答非所问"}, headers=_H)
    assert r.status_code == 200
    rows = await db.fetch_all("SELECT rating, reason FROM message_feedback WHERE conversation_id=:c", {"c": cid})
    assert rows and rows[0]["rating"] == "down"


async def test_feedback_rejects_bad_rating(seeded_db):
    from ai_engine import main as main_mod
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        init = await client.post("/api/v1/conversations", json={}, headers=_H)
        cid = init.json()["conversation_id"]
        r = await client.post(f"/api/v1/conversations/{cid}/feedback",
                              json={"message_id": 1, "rating": "meh"}, headers=_H)
    assert r.status_code == 400
```
注：conversations 创建需绑定 BU00243780（seeded_db + X-BU-ID）。

- [ ] **Step 2: 跑测试确认失败** → `pytest tests/test_feedback.py -v` FAIL
- [ ] **Step 3: 实现 feedback.py / api/feedback.py / 注册路由**
- [ ] **Step 4: 跑测试通过** → `pytest tests/test_feedback.py -v` PASS
- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/feedback.py server/src/ai_engine/api/feedback.py server/src/ai_engine/main.py server/tests/test_feedback.py
git commit -m "feat(feedback): 消息级 👍/👎 反馈落库 + 端点 + 计数"
```

---

## Task 7: 知识缺口聚合查询 + 端点

**Files:**
- Create: `server/src/ai_engine/persistence/insights.py`
- Create: `server/src/ai_engine/api/insights.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_insights.py`（新建）

insights.py（按 created_at 字符串窗口过滤，沿用项目时间列约定）：
```python
from typing import Any
from ai_engine.persistence import db


def _range(date_from: str | None, date_to: str | None) -> tuple[str, dict[str, Any]]:
    clause, params = "", {}
    if date_from:
        clause += " AND created_at >= :df"; params["df"] = date_from
    if date_to:
        clause += " AND created_at <= :dt"; params["dt"] = date_to
    return clause, params


async def knowledge_gaps(date_from: str | None, date_to: str | None) -> dict[str, Any]:
    rng, p = _range(date_from, date_to)
    out_of_scope = await db.fetch_one(
        f"SELECT COUNT(*) AS n FROM messages WHERE role='user' AND topic_verdict='no'{rng}", p)
    failed = await db.fetch_one(
        f"SELECT COUNT(*) AS n FROM messages WHERE role='user' AND status='failed'{rng}", p)
    thumbs_down = await db.fetch_one(
        f"SELECT COUNT(*) AS n FROM message_feedback WHERE rating='down'{rng}", p)
    no_info = await db.fetch_one(
        f"SELECT COUNT(*) AS n FROM tickets WHERE created_at IS NOT NULL{rng} "
        "AND payload_json LIKE '%\"category\": \"\\u65e0\\u4fe1\\u606f\"%' ESCAPE '\\'", p)
    # 注：category 中文「无信息」在 payload_json 里可能被 ensure_ascii 转义；改用更稳的 current_severity 无法判分类，
    # 故 no_info 用 LIKE 匹配 category 字段两种可能写法
    return {
        "out_of_scope": int(out_of_scope["n"]) if out_of_scope else 0,
        "failed_turns": int(failed["n"]) if failed else 0,
        "thumbs_down": int(thumbs_down["n"]) if thumbs_down else 0,
    }
```
注：「无信息」工单计数对 payload_json LIKE 中文转义不稳，且 create_ticket 写库格式需先确认；为避免脆弱查询，**本任务 no_info 暂不纳入聚合**，只输出 out_of_scope / failed_turns / thumbs_down 三项可靠信号。后续若需要按工单分类统计，应在 tickets 表加独立 category 列（另开任务）。

最终 insights.py 的 knowledge_gaps 只返回三项（去掉 no_info 查询）。

api/insights.py（staff 鉴权，仿 staff_kpi）：
```python
from typing import Any
from fastapi import APIRouter, Depends, Query
from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence.insights import knowledge_gaps

router = APIRouter()


@router.get("/staff/api/v1/insights/knowledge-gaps")
async def gaps(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(require_staff),
) -> dict[str, Any]:
    return {"from": date_from, "to": date_to, **(await knowledge_gaps(date_from, date_to))}
```

- [ ] **Step 1: 写失败测试**

```python
async def test_knowledge_gaps_counts(seeded_db):
    from ai_engine.persistence import conversations as c, feedback as fb, insights
    t1 = await c.append_user_turn(1, "范围外", "k1"); await c.set_turn_verdict(t1, "no"); await c.finalize_turn(t1, "done")
    t2 = await c.append_user_turn(1, "崩了", "k2"); await c.finalize_turn(t2, "failed", "INTERNAL_ERROR")
    mid = await c.append_message(1, "assistant", "x")
    await fb.add_feedback(1, mid, "down", "不准", "BU00243780", "b")
    g = await insights.knowledge_gaps(None, None)
    assert g["out_of_scope"] == 1
    assert g["failed_turns"] == 1
    assert g["thumbs_down"] == 1
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现 insights.py（三项）/ api/insights.py / 注册路由**
- [ ] **Step 4: 跑测试通过** → PASS
- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/insights.py server/src/ai_engine/api/insights.py server/src/ai_engine/main.py server/tests/test_insights.py
git commit -m "feat(insights): 知识缺口聚合(范围外/失败回合/差评) + staff 端点"
```

---

## Task 8: 僵尸回合清理 + 后台任务

**Files:**
- Create: `server/src/ai_engine/persistence/maintenance.py`
- Modify: `server/src/ai_engine/config.py`（加配置）
- Modify: `server/src/ai_engine/main.py`（startup 起后台任务 + shutdown 取消）
- Test: `server/tests/test_maintenance.py`（新建）

config.py 追加：
```python
    stale_turn_timeout_seconds: int = 120  # 回合处理中超过此时长视为僵尸，标 failed
    stale_sweep_interval_seconds: int = 60  # 后台清理扫描间隔；<=0 关闭
```

maintenance.py：
```python
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

logger = logging.getLogger(__name__)


async def reclaim_stale_turns(timeout_seconds: int) -> int:
    """把 processing 且 created_at 早于 cutoff 的 user 回合标 failed，返回清理条数。"""
    cutoff = (datetime.now(UTC) - timedelta(seconds=timeout_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.fetch_all(
        "SELECT id FROM messages WHERE role='user' AND status='processing' AND created_at < :c",
        {"c": cutoff},
    )
    if not rows:
        return 0
    await db.execute(
        "UPDATE messages SET status='failed', error_code='STALE_RECLAIMED' "
        "WHERE role='user' AND status='processing' AND created_at < :c",
        {"c": cutoff},
    )
    n = len(rows)
    metrics.stale_turns_reclaimed_total.inc(n)
    logger.warning("reclaimed %d stale turns (cutoff=%s)", n, cutoff)
    return n


async def sweep_loop() -> None:
    interval = settings.stale_sweep_interval_seconds
    if interval <= 0:
        return
    while True:
        try:
            await reclaim_stale_turns(settings.stale_turn_timeout_seconds)
        except Exception:
            logger.exception("stale sweep iteration failed")
        await asyncio.sleep(interval)
```
注：`now_str` import 仅为风格一致，可去掉若未用。cutoff 用同格式字符串比较（库里 created_at 同宽度格式，字典序==时间序）。

main.py startup 末尾追加后台任务，并加 shutdown 取消：
```python
import asyncio
from ai_engine.persistence.maintenance import sweep_loop

_sweep_task: asyncio.Task | None = None

@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    await init_business_dbs(settings.unlimitpay_db_url, settings.nexus_db_url)
    global _sweep_task
    if settings.stale_sweep_interval_seconds > 0:
        _sweep_task = asyncio.create_task(sweep_loop())

@app.on_event("shutdown")
async def _shutdown() -> None:
    global _sweep_task
    if _sweep_task:
        _sweep_task.cancel()
```
（现有 _startup 已存在，合并而非重复定义。）

- [ ] **Step 1: 写失败测试**

```python
async def test_reclaim_marks_old_processing_failed(seeded_db):
    from ai_engine.persistence import conversations as c, db
    from ai_engine.persistence.maintenance import reclaim_stale_turns
    tid = await c.append_user_turn(1, "卡住的", "stale-1")
    # 手动把 created_at 改成很久以前
    await db.execute("UPDATE messages SET created_at='2000-01-01 00:00:00' WHERE id=:id", {"id": tid})
    n = await reclaim_stale_turns(120)
    assert n == 1
    rows = await c.list_messages(1)
    turn = [r for r in rows if r["id"] == tid][0]
    assert turn["status"] == "failed"
    assert turn["error_code"] == "STALE_RECLAIMED"


async def test_reclaim_keeps_recent_processing(seeded_db):
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence.maintenance import reclaim_stale_turns
    tid = await c.append_user_turn(1, "刚发的", "fresh-1")
    assert await reclaim_stale_turns(120) == 0
    rows = await c.list_messages(1)
    assert [r for r in rows if r["id"] == tid][0]["status"] == "processing"
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现 maintenance.py + config + main.py 合并 startup/shutdown**
- [ ] **Step 4: 跑测试 + 全量回归**

Run: `cd server && .venv/bin/pytest tests/test_maintenance.py tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/maintenance.py server/src/ai_engine/config.py server/src/ai_engine/main.py server/tests/test_maintenance.py
git commit -m "feat(reliability): 僵尸回合(processing 超时)后台清理 + 配置"
```

---

## Task 9: 后端全量回归 + lint

**Files:** 无新增，仅校验

- [ ] **Step 1: 全量测试**

Run: `cd server && .venv/bin/pytest -q`
Expected: 全绿（docker 相关 mysql/postgres 用例可能 skip，正常）。

- [ ] **Step 2: lint/format**

Run: `cd server && .venv/bin/ruff check src tests && .venv/bin/ruff format src tests`
Expected: 无错误（format 仅本轮改动文件）。

- [ ] **Step 3: Commit（若 format 有改动）**

```bash
git add -A server && git commit -m "style: ruff format 本轮可靠性改动"
```

---

## Task 10: 前端 client_message_id + 反馈按钮

**Files:**
- Modify: `web/src/api/chat.ts`（streamChat 带 client_message_id；新增 sendFeedback）
- Modify: `web/src/hooks/useChat.ts`（send 生成 client_message_id）
- Modify: `web/src/components/MessageBubble.tsx` 或 `ChatExtras.tsx`（assistant 消息加 👍/👎）
- Test: `web/tests/*`（vitest，仿现有）

设计：
1. `streamChat` 入参加 `clientMessageId?: string`，拼到 URL query。
2. `useChat.send` 用 `crypto.randomUUID()` 生成 id，传入 streamChat。（当前 send 不自动重试，主要用于去重；保持简单。）
3. 新增 `sendFeedback(conversationId, messageId, rating, reason?)` → POST `/api/v1/conversations/{id}/feedback`。
4. 反馈 UI：assistant 气泡下加两个小按钮，点击调 sendFeedback；本地标记已反馈避免重复。messageId 来源——前端消息列表当前无 server id；最小实现用消息在列表中的 index 作 message_id 占位（后端 message_id 仅做关联记录，不强校验存在性）。

注：前端消息无真实 DB message_id 是已知限制；本任务用 index 占位，后端 add_feedback 不做 FK 存在校验失败处理（DB FK 约束在 SQLite 默认不强制，PG 下需确保 message_id 存在——故后端 message_id 允许指向任意值有风险）。**取舍**：把 message_feedback.message_id 的 FK 在 schema 中保留但前端传 0 占位会违反 PG FK。改为：前端传当前 assistant 在列表的展示序号，后端 add_feedback 前用 `conversation_id` 关联即可，message_id 记录"第几条"。为避免 PG FK 违例，**Task 1 的 message_feedback.message_id 去掉 ForeignKey 约束，仅作 Integer 记录列**。

⚠️ 回填 Task 1：`message_feedback.message_id` 用 `Column("message_id", Integer, nullable=False)`（不加 ForeignKey），避免前端无真实 id 时违反 PG 外键。

- [ ] **Step 1: chat.ts 改 streamChat + 加 sendFeedback**

```typescript
export async function* streamChat(args: {
  conversationId: number;
  message: string;
  lastEventId?: string;
  clientMessageId?: string;
}): AsyncGenerator<ChatEvent> {
  let url = `/api/v1/chat?conversation_id=${args.conversationId}&message=${encodeURIComponent(args.message)}`;
  if (args.clientMessageId) url += `&client_message_id=${encodeURIComponent(args.clientMessageId)}`;
  const headers: Record<string, string> = {};
  if (args.lastEventId) headers["Last-Event-ID"] = args.lastEventId;
  const resp = await authedFetch(url, { headers });
  if (!resp.ok || !resp.body) throw new Error(`chat http ${resp.status}`);
  yield* readSseStream(resp);
}

export async function sendFeedback(
  conversationId: number, messageId: number,
  rating: "up" | "down", reason?: string,
): Promise<void> {
  await authedFetch(`/api/v1/conversations/${conversationId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, rating, reason }),
  });
}
```

- [ ] **Step 2: useChat.send 生成 client_message_id**

send 内 streamChat 调用加：
```typescript
const cmid = crypto.randomUUID();
for await (const ev of streamChat({
  conversationId: init.conversation_id,
  message: text,
  lastEventId: lastEventIdRef.current,
  clientMessageId: cmid,
})) { ... }
```

- [ ] **Step 3: 反馈 UI（MessageBubble 或 ChatExtras）**

在 assistant 气泡渲染处加两个按钮（👍/👎），点击调 `sendFeedback(convId, idx, rating)`，用本地 state 标记已点。具体实现按现有组件结构对齐（读 MessageBubble.tsx 后落地）。

- [ ] **Step 4: 前端类型 + 测试 + 构建**

Run: `cd web && pnpm type-check && pnpm test && pnpm build`
Expected: type-check 通过；vitest 通过；build 出 dist。

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): 发送带 client_message_id(幂等) + 消息 👍/👎 反馈"
```

---

## Self-Review 结论

- 留痕缺口：#1 verdict 落库(Task4)+计数(Task3)✓；#2 反馈(Task6+10)✓；#3 知识缺口报表(Task7)✓。
- 兜底缺口：#4 状态机(Task1/2/4)✓；#5 fail-soft(Task4/5)✓；#6 幂等(Task1/2/5/10)✓；#7 僵尸清理(Task8)✓。
- 取舍记录：知识缺口报表暂不含「无信息」工单分类(payload_json LIKE 脆弱)；message_feedback.message_id 不加 FK(前端无真实 id)。两处均在对应任务标注，列为后续改进。
- 跨端契约：新增 query 参数 client_message_id(后端可选，前端补发)；新增 POST /feedback 端点(前后端同步在 Task6/10)。
