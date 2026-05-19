# Task 12: Prometheus /metrics endpoint + 指标埋点

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Add deps: `prometheus_client>=0.20`
- Create: `src/ai_engine/observability/metrics.py`
- Create: `src/ai_engine/api/metrics.py`
- 全代码插埋点（runtime / tool_router / chat 端点等）

- [ ] **Step 1: 关键指标定义**

```python
# observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# 实时
active_conversations = Gauge("ai_engine_active_conversations", "当前活跃对话数")
human_pending = Gauge("ai_engine_human_pending", "等待人工接管的会话数")

# 工具调用
tool_calls = Counter("ai_engine_tool_calls_total", "工具调用次数", ["tool", "ok"])
tool_duration = Histogram("ai_engine_tool_duration_seconds", "工具耗时", ["tool"])

# LLM 成本
llm_tokens = Counter("ai_engine_llm_tokens_total", "LLM token 消耗", ["model", "kind"])
llm_calls = Counter("ai_engine_llm_calls_total", "LLM 调用次数", ["model"])

# 工单
tickets_created = Counter("ai_engine_tickets_total", "工单创建", ["category", "severity", "user_type"])
ticket_resolution_seconds = Histogram("ai_engine_ticket_resolution_seconds",
                                       "工单解决耗时", ["category"])

# 客服
staff_takeovers = Counter("ai_engine_staff_takeovers_total", "客服接管次数", ["staff_id"])
staff_takeover_duration = Histogram("ai_engine_staff_takeover_seconds",
                                     "客服接管时长", ["staff_id"])

# 用户满意度
user_resolved_total = Counter("ai_engine_user_resolved_total", "用户标记解决", ["event"])
```

- [ ] **Step 2: 端点**

```python
# api/metrics.py
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

- [ ] **Step 3: 插埋点**

- runtime.run_turn: 进入时 `active_conversations.inc()`；结束 `dec()`；每轮 LLM 后 `llm_tokens.inc(input_tokens, kind="input")` 等
- tool_router.dispatch: `tool_calls.labels(tool=name, ok=ok).inc()` + `tool_duration.observe(duration)`
- create_ticket: `tickets_created.labels(...).inc()`
- staff_conversations.take/release: 接管时记起始时间，释放时 `staff_takeover_duration.observe(...)`
- user-events: `user_resolved_total.labels(event=...).inc()`

- [ ] **Step 4: 测试 + Commit**

```bash
git commit -m "feat(mvp-3): /metrics endpoint + 关键指标埋点（runtime/tools/tickets/staff）"
```

---
