# 管理后台可观测性整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`).

**Goal:** 让 CS 工作台从"只记录执行/人工动作"升级到"能照见 AI 答得对不对"——把已落库但没读出来的质量信号（空结果/失败/判定/差评/转人工）接到运营视图、可下钻、接动作，并把 prompt 灰度闭环。

**Architecture:** 共享地基先行（`tool_audits` 增 `result_count`/`is_empty`/`subject_id`/`user_type`；`messages` 增 `prompt_version`），其上分功能改造（工具审计 UI/会话列表质量信号/知识缺口可执行/KPI 质量指标/反馈接动作/灰度闭环/工单只读/旁观结果可见）。每改一个数据列：改 `schema.py` Table 定义 + 加 alembic 迁移。

**Tech Stack:** FastAPI + SQLAlchemy Core(metadata.create_all) + Alembic / pytest / React+TS(web) / 业务只读库 aiomysql。

**关键评审依据（执行时作背景，不要推翻）：**
- 五个功能共同盲点：记"跑没跑/人工动作"，照不到"ok 但查空/答错"。最近的 bug 发生时盘面全绿。
- 质量信号已在库：`messages.status='failed'`、`messages.topic_verdict='no'`、`message_feedback.rating='down'`、`conversations.mode='human_pending'`、`tool_audits`。缺的是 join/暴露/下钻/接动作。
- 工具空结果不抛异常（`query_kyc` 查空 return `{"kyc":None}`、`query_transaction` 返回 `{"card_count":0,...}`），所以 `rejected=0`、`result_size>0`，审计看不出。

**判断取舍（已定，执行照做）：**
- 工单：外部"事项中心"是状态真源，本地是镜像；只补**只读列表**给运营，不做本地强状态机。
- 多副本：当前单副本，灰度热加载/旁观 firehose 的跨副本问题只加注释/TODO，不实做跨副本桥。
- `result_count` 由 dispatch 用统一 helper 从返回值推断，不逐个改工具 handler。

---

## 执行约定（通用）

**工作目录** `server/`（=`.../reliability-hardening/server`）。命令用 `.venv/bin/python`、`.venv/bin/pytest`。前端在 `web/`，用 `pnpm`（type-check：`pnpm -C web tsc --noEmit` 或项目既有脚本；先看 `web/package.json`）。

**加 DB 列的标准动作（每次）：**
1. 改 `server/src/ai_engine/persistence/schema.py` 对应 Table 定义（新增 Column）。
2. 新建 alembic 迁移：`server/migrations/versions/<rev>_xxx.py`，`down_revision` 指向当前最新（现为 `999833d7e011`，若前序任务已加迁移则指向它——执行时先 `ls -t migrations/versions/` 确认链尾）。`upgrade()` 用 `op.add_column(...)`，`downgrade()` 用 `op.drop_column(...)`。
3. 测试用 `init_db`(create_all) 在全新库建表即含新列，单测无需跑迁移；但**部署**需 `alembic upgrade head`。

**测试 DB**：用既有 `temp_db_url` fixture + `init_db()`（见 `tests/test_tool_router_injection.py` 范式）。

**前端**：改完跑 type-check；不确定脚本名先读 `web/package.json`。

---

## Phase 0 — 地基：工具审计记录结果质量与身份

### Task 0.1: tool_audits 增列 result_count / is_empty / subject_id / user_type

**Files:** `server/src/ai_engine/persistence/schema.py`、`server/migrations/versions/<rev>_audit_quality_cols.py`、`server/tests/test_persistence_schema.py`(加断言)

- [ ] **Step 1: 失败测试** 在 `tests/test_audit_quality.py` 新建：
```python
import pytest
pytestmark = pytest.mark.asyncio

async def test_log_tool_call_persists_quality_fields(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence import audit
    await init_db()
    await audit.log_tool_call(
        conversation_id=1, tool_name="query_kyc", params={"user_id": "212433"},
        result_size=20, duration_ms=5, rejected=False, reject_reason=None,
        result_count=0, is_empty=True, subject_id="212433", user_type="c",
    )
    rows = await audit.list_audits(1)
    assert rows[0]["result_count"] == 0 and rows[0]["is_empty"] in (1, True)
    assert rows[0]["subject_id"] == "212433" and rows[0]["user_type"] == "c"
```
- [ ] **Step 2: 跑→FAIL**（`log_tool_call` 不接受新参数 / 列不存在）。
- [ ] **Step 3: 实现**：
  - `schema.py` 的 `tool_audits` Table 增：`Column("result_count", Integer, nullable=True)`、`Column("is_empty", Integer, nullable=True)`、`Column("subject_id", String(128), nullable=True)`、`Column("user_type", String(8), nullable=True)`。
  - alembic 迁移 add_column 这四列（nullable，便于历史行）。
  - `audit.py`：`log_tool_call` 增形参 `result_count: int | None = None, is_empty: bool | None = None, subject_id: str | None = None, user_type: str | None = None`，INSERT 增这四列；`list_audits`/`recent_audits`/`_RECENT_*` 的 SELECT 增这四列。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(audit): tool_audits 记录 result_count/is_empty/subject_id/user_type`

### Task 0.2: dispatch 计算结果质量并落审计

**Files:** `server/src/ai_engine/agent/tool_router.py`、`server/tests/test_tool_router_c_identity.py`(扩展) 或新 `tests/test_tool_router_result_count.py`

- [ ] **Step 1: 失败测试**：
```python
async def test_empty_result_logged_as_empty(temp_db_url, monkeypatch):
    from ai_engine.agent import tool_router
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db
    import ai_engine.persistence.audit as audit
    await init_db()
    async def h(user_id, **k): return {"kyc": None, "note": "无记录"}
    base.register(base.Tool(name="q_empty", description="x",
        input_schema={"type":"object","properties":{}}, handler=h,
        requires_subject_id=True, subject_field="user_id"))
    await tool_router.dispatch(tool_name="q_empty", params={}, user_type="c",
        subject_id="999", conversation_id=1)  # 999 纯数字跳翻译
    rows = await audit.list_audits(1)
    assert rows[-1]["is_empty"] in (1, True) and rows[-1]["result_count"] == 0
    assert rows[-1]["subject_id"] == "999" and rows[-1]["user_type"] == "c"
```
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现** 在 `tool_router.py`：
  - 加 helper：
```python
def _result_count(data: object) -> int:
    """从工具返回推断"有效结果条数"：优先 *_count 整数之和；否则 list 值长度之和；
    dict 型记录(如 {"kyc": {...}}) 非空记 1、None/空记 0。"""
    if not isinstance(data, dict):
        return 1 if data else 0
    count_keys = [v for k, v in data.items() if k.endswith("count") and isinstance(v, int)]
    if count_keys:
        return sum(count_keys)
    lists = [v for v in data.values() if isinstance(v, list)]
    if lists:
        return sum(len(v) for v in lists)
    records = [v for k, v in data.items()
               if k not in ("note", "unmasked", "pii_note") and v not in (None, {}, [])]
    return 1 if records else 0
```
  - 成功路径 `log_tool_call(...)` 传 `result_count=_result_count(data)`、`is_empty=(_result_count(data)==0)`、`subject_id=subject_id`、`user_type=user_type`。被拒/异常路径也补 `subject_id=subject_id, user_type=user_type`（result_count=0,is_empty=True）。
- [ ] **Step 4: 跑→PASS** + 跑 `tests/test_tool_router_*.py` 全绿。
- [ ] **Step 5: Commit** `feat(audit): dispatch 记录工具结果条数/空结果/身份`

### Task 0.3: messages 增 prompt_version 并写入

**Files:** `schema.py`、新迁移、`server/src/ai_engine/persistence/conversations.py`(写消息处)、`server/src/ai_engine/agent/runtime.py`(finalize)、`tests/test_turn_lifecycle.py`(加断言)

- [ ] **Step 1: 失败测试**：断言 assistant 消息行带 `prompt_version`（在既有回合生命周期测试里加：跑一轮后查 messages 最新 assistant 行 `prompt_version` 非空）。先读 `tests/test_turn_lifecycle.py` 与 `conversations.py` 写 assistant 消息的函数签名，按真实签名写断言。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：`messages` 表加 `Column("prompt_version", String(16))` + 迁移；写 assistant 消息的持久化函数增 `prompt_version` 参数；`runtime.py` finalize 时把本轮 `prompt_version`（已在 `run_turn` 算出，约 212 行）传下去落库。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(prompt): assistant 消息落 prompt_version，为灰度 A/B 评估打底`

---

## Phase 1 — 工具审计 UI：空结果可见 + 筛选/分页

### Task 1.1: recent_audits 支持筛选与分页

**Files:** `server/src/ai_engine/persistence/audit.py`、`server/src/ai_engine/api/staff_logs.py`、`tests/test_staff_logs.py`

- [ ] **Step 1: 失败测试**：调 `recent_audits(limit=50, rejected_only=False, tool_name="query_kyc", empty_only=True, conversation_id=None, before_id=None)` 只返回 query_kyc 且 is_empty 的行；分页 `before_id` 返回更早的行。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：`recent_audits` 增可选 `tool_name`/`empty_only`/`conversation_id`/`before_id`（游标分页：`id < :before_id`）。**用参数化绑定 + 条件拼装 WHERE（仅在参数非空时追加固定片段，绝不拼用户串）**，沿用文件内"恒定绑定避免动态拼 SQL"的风格（白名单字段）。`staff_logs.py` 的全局审计端点把这些作为 query 参数透传（limit 钳制保留）。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(audit): 全局审计支持按工具/空结果/会话筛选 + 游标分页`

### Task 1.2: 前端审计页显示结果条数 + 标红空结果 + 筛选

**Files:** `web/src/routes/staff/AuditsRoute.tsx`、`web/src/routes/staff/ConversationLogsRoute.tsx`、`web/src/lib`(API 调用与类型, grep `ToolAudit`/`recentAudits`/`staff.ts`)

- [ ] **Step 1**: 先读 `web/src/.../staff.ts`(类型+API) 与两个路由现状。
- [ ] **Step 2**: `ToolAudit` 类型加 `result_count?: number; is_empty?: boolean; subject_id?: string; user_type?: string`；API 函数加筛选参数。
- [ ] **Step 3**: AuditsRoute 表格加"返回"列（显示 `result_count` 条；`is_empty` 时整行/该列用错误色标红，文案如 `0 条 空`）；筛选区加工具下拉（query_*/create_ticket 等）、"只看空结果"复选框、会话号输入；底部"加载更多"用 `before_id` 游标。ConversationLogsRoute 的工具调用块同样显示返回条数 + 空结果标红 + 注入的 subject_id。
- [ ] **Step 4**: 跑前端 type-check 通过；本地 dev 眼检。
- [ ] **Step 5: Commit** `feat(web): 审计页显示返回条数+标红空结果+按工具/空/会话筛选`

---

## Phase 2 — 会话列表暴露质量信号 + 风险筛选

### Task 2.1: list_for_staff join 风险信号

**Files:** `server/src/ai_engine/persistence/conversations.py`、`server/src/ai_engine/api/staff_conversations.py`、`tests/test_conversations_api.py` 或新 `tests/test_conversation_risk_signals.py`

- [ ] **Step 1: 失败测试**：构造一个 `mode='ai'` 会话，含一条 `status='failed'` 消息（或一条 👎 反馈），调列表（`risk_only=True`）应能返回该会话且带 `has_failed`/`has_downvote`/`has_out_of_scope` 标记；普通 `mode` 过滤不变。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：`list_for_staff` 增 `risk_only: bool=False`。SQL LEFT JOIN/子查询计算每会话是否有：`messages.status='failed'`、`messages.topic_verdict='no'`、`message_feedback.rating='down'`、`tool_audits.is_empty=1`。返回字段加这四个布尔（或一个 `risk_flags`）。`risk_only=True` 时只返回任一为真的会话（**含 mode='ai' 的**，突破现有 `mode!='ai'` 限制——风险信号路径单独查）。端点加 `risk_only` 参数。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(staff): 会话列表暴露失败/差评/范围外/空结果风险信号 + risk_only 筛选`

### Task 2.2: 前端会话列表风险角标 + 风险筛选页

**Files:** `web/src/routes/staff/ConversationsListRoute.tsx`、`web/src/.../staff.ts`(类型)

- [ ] **Step 1**: 读现状。
- [ ] **Step 2**: 列表类型加风险字段；列表项渲染风险角标（失败/差评/范围外/空结果，用警示色）；筛选区加"有风险信号"选项（调 `risk_only=true`）。
- [ ] **Step 3**: type-check + 眼检。
- [ ] **Step 4: Commit** `feat(web): 会话列表风险角标 + 有风险信号筛选`

---

## Phase 3 — 反馈接动作（👎 不再是黑洞）

### Task 3.1: 👎 触发告警 + 标记会话待复核

**Files:** `server/src/ai_engine/api/feedback.py`、`server/src/ai_engine/persistence/conversations.py`(标记)、`server/src/ai_engine/integrations`(Lark, grep `lark`/`webhook`)、`tests/test_feedback.py`

- [ ] **Step 1**: 先读 `feedback.py` 现状 + `create_ticket.py` 里 Lark 发送的工具函数（复用）。
- [ ] **Step 2: 失败测试**：提交 `rating='down'` 后，(a) 调用了 Lark 告警函数（monkeypatch 断言被调用，带会话/原因）；(b) 该会话被标记 `needs_review`（新增轻量标记：conversations 增 `needs_review` 列，或写入一张 review 队列——**选 conversations 增列**，最简且能被 Phase2 风险筛选复用）。
- [ ] **Step 3: 实现**：
  - `conversations` 表加 `Column("needs_review", Integer, server_default="0")` + 迁移。
  - `feedback.py` 在 `rating=='down'` 时：调 Lark 告警（复用既有发送函数，失败不阻断主流程，try/except + log）；`UPDATE conversations SET needs_review=1`。
  - Phase 2 的 `risk_only` 查询把 `needs_review=1` 也纳入风险信号。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(feedback): 差评触发 Lark 告警 + 标记会话待复核`

---

## Phase 4 — 知识缺口可执行化

### Task 4.1: 后端按工具聚合空结果/失败率 + 纳入转人工 + 时间窗 + 下钻

**Files:** `server/src/ai_engine/persistence/insights.py`、`server/src/ai_engine/api/insights.py`、`tests/test_insights.py`

- [ ] **Step 1: 失败测试**：
  - `tool_health(from,to)` 返回按 `tool_name` 分组的 `{calls, empty, rejected, empty_rate}`（来自 `tool_audits`，依赖 Phase0 的 is_empty）。
  - `knowledge_gaps` 增 `human_handoff`（`conversations.mode IN ('human_pending','human_takeover')` 计数）。
  - 新增 `gap_conversations(kind, from, to)` 返回某类缺口的 conversation_id 列表（下钻）。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：insights.py 加上述查询（全部结构化、参数化、带时间窗）；`failed_turns` 拆出 `error_code`/STALE_RECLAIMED 与真实失败分开统计（读现有 status/error_code 写入）；api/insights.py 暴露 `tool_health`、`gap_conversations` 端点并把前端会传的 `from/to` 接上。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(insights): 知识缺口加工具空结果率/转人工/时间窗/下钻会话`

### Task 4.2: 前端知识缺口可下钻 + 工具健康 + 时间窗

**Files:** `web/src/routes/staff/InsightsRoute.tsx`、`web/src/.../staff.ts`

- [ ] **Step 1**: 读现状。
- [ ] **Step 2**: 三张卡片改为可点击 → 下钻到对应会话清单（调 `gap_conversations`）；新增"工具健康"表（各工具 calls/空结果率，空结果率高的标红）；加时间窗选择（默认近 7 天，传 `from/to`），去掉"全部历史"写死。
- [ ] **Step 3**: type-check + 眼检。
- [ ] **Step 4: Commit** `feat(web): 知识缺口可下钻 + 工具健康表 + 时间窗`

---

## Phase 5 — KPI 补 AI 质量指标 + 修口径

### Task 5.1: KPI 增 AI 质量指标并修比率口径

**Files:** `server/src/ai_engine/persistence/staff_metrics.py`、`server/src/ai_engine/api/staff_kpi.py`、`tests/test_staff_kpi`(grep 现有测试)

- [ ] **Step 1: 失败测试**：KPI 返回新增全局 AI 质量块 `ai_quality`：`handoff_rate`(转人工会话/总会话)、`downvote_rate`(👎/(👍+👎))、`tool_empty_rate`(空结果工具调用/工具调用)、`out_of_scope`/`failed_turns`(复用 insights)。并断言 `resolved_ratio` 口径修正（见 step3）。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：staff_metrics/staff_kpi 增 `ai_quality` 聚合（复用 insights 查询 + tool_audits + message_feedback + conversations）；修 `resolved_ratio`/`release_ratio` 分母：把 `transfer_out` 消费的 take 从分母剔除或单列 `transfer_ratio`，使分子分母口径一致（在文件内注释清楚口径）。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(kpi): 增 AI 质量指标(转人工/差评/空结果率)+修接管比率口径`

### Task 5.2: 前端 KPI 展示 AI 质量 + 接时间窗

**Files:** `web/src/routes/staff/KpiRoute.tsx`、`web/src/.../staff.ts`

- [ ] **Step 1-3**: 读现状 → 加"AI 质量"区块（转人工率/差评率/空结果率/范围外/失败，比率类<阈值绿、超标红）+ 日期范围选择器（后端已支持 from/to）；type-check + 眼检。
- [ ] **Step 4: Commit** `feat(web): KPI 展示 AI 质量指标 + 日期筛选`

---

## Phase 6 — Prompt 灰度闭环 + 审计

### Task 6.1: 灰度变更审计留痕 + 保存校验

**Files:** `server/src/ai_engine/prompts/registry.py`、`server/src/ai_engine/api/admin_prompts.py`、`tests/test_prompt_registry.py`/`test_admin_prompts.py`

- [ ] **Step 1: 失败测试**：调 `update_rollout` 后产生一条审计记录（who/when/old→new）；指向缺失 .md 的版本时保存报错（校验 prompt_key 文件存在）。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：`update_rollout` 增校验：遍历受影响版本的全部 prompt_key，`file_path(...).exists()` 否则 raise；admin_prompts 端点在改灰度成功后写一条审计（复用 tool_audits？不合适——新建轻量 `prompt_change_log` 表或写 app 日志 + 一个查询端点。**最简：新建 `prompt_changes` 表**(id, actor, old_json, new_json, created_at) + 在端点记录 actor(来自 require_admin 的身份)）。
- [ ] **Step 4: 跑→PASS**。
- [ ] **Step 5: Commit** `feat(prompt): 灰度变更留痕 + 保存校验文件存在`

### Task 6.2: 按 prompt_version 的效果对比端点 + 前端展示

**Files:** `server/src/ai_engine/api/admin_prompts.py`(或 insights)、`web/src/routes/admin/PromptsRoute.tsx`

- [ ] **Step 1: 失败测试**：`prompt_ab_stats(from,to)` 按 `messages.prompt_version`(Phase0.3) 分组返回 `{version: {turns, failed_rate, downvote_rate, handoff_rate}}`。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：聚合查询 join messages.prompt_version × status/feedback/conversations.mode；端点暴露；PromptsRoute 在灰度配置下方加"各版本表现"对比表。
- [ ] **Step 4: 跑→PASS** + type-check。
- [ ] **Step 5: Commit** `feat(prompt): 按版本的 A/B 效果对比(失败/差评/转人工率)`

---

## Phase 7 — 旁观结果可见 + 连接泄漏修复

### Task 7.1: tool_result 事件带空结果 + 前端显示 + abort 修复

**Files:** `server/src/ai_engine/agent/runtime.py`(tool_result 事件, ~518)、`web/src/routes/staff/SpectateRoute.tsx`、`web/src/.../staff.ts`(streamSse)

- [ ] **Step 1**: 读 runtime tool_result 事件构造处 + SpectateRoute + streamSse。
- [ ] **Step 2: 失败测试**（后端）：tool_result 事件 payload 含 `ok` 与 `empty`(或 `result_count`)。
- [ ] **Step 3: 实现**：runtime 推 tool_result 时带 `result_count`/`empty`(dispatch 已知)；SpectateRoute labeler 显示 `工具返回：{name}（{n} 条/空，ok）`，空结果标警示色；`streamSse` 接 `AbortController`，SpectateRoute cleanup 时 abort（修切会话/StrictMode 连接泄漏）。
- [ ] **Step 4: 跑→PASS** + type-check。
- [ ] **Step 5: Commit** `feat(spectate): 旁观显示工具返回条数/空结果 + 修 SSE 连接泄漏`

---

## Phase 8 — 工单只读列表（运营可见）

### Task 8.1: 工单列表端点 + 前端工单页

**Files:** `server/src/ai_engine/api/tickets.py`、`server/src/ai_engine/persistence`(tickets 查询)、`web/src/routes/staff/TicketsRoute.tsx`(新)、路由注册(grep router 注册处)、`tests/test_tickets_callback.py` 或新 `tests/test_tickets_list.py`

- [ ] **Step 1: 失败测试**：`GET /staff/api/v1/tickets?open=true&severity=p1` 返回工单列表（external_id/category/severity/是否关闭/created_at/conversation_id），关闭态由 `NOT EXISTS(event='closed')` 现算（沿用现有逻辑）。
- [ ] **Step 2: 跑→FAIL**。
- [ ] **Step 3: 实现**：persistence 加 `list_tickets(open_only, severity, category, limit, before_id)`；tickets.py 加只读 GET 端点（staff 鉴权）；前端新增 TicketsRoute（列表 + 过滤 + 点击跳会话留痕），加进 staff 导航与路由表。
- [ ] **Step 4: 跑→PASS** + type-check。
- [ ] **Step 5: Commit** `feat(tickets): 运营只读工单列表(过滤/跳会话)`

---

## Phase 9 — 回归 + 部署

- [ ] **Step 1**: 后端全量 `.venv/bin/pytest -q`（已知 `test_tickets_callback` 2 个为 baseline 预存失败，需确认未新增失败）。
- [ ] **Step 2**: 前端 `pnpm -C web` type-check + 构建。
- [ ] **Step 3**: 部署：FF 合并到 main → 对运行库跑 `alembic upgrade head`（新列）→ `docker compose up -d --build api`（按 [[backend-docker-rebuild]]）→ 重建前端 dist（若 webview 用 dist）。验证 /metrics 200 + 容器内含新代码 + 抽查一个真实会话审计能看到空结果标记。

---

## Self-Review
- **覆盖**：五个功能各有任务（审计 P0+P1、会话列表 P2、反馈 P3、知识缺口 P4、KPI P5、灰度 P6、旁观 P7、工单 P8），共同地基在 P0。
- **占位符**：列名/字段/端点参数/测试断言均具体；个别"先读现状再按真实签名"是有意（写消息函数、Lark 发送函数、前端 staff.ts、router 注册——执行时读真实签名），非 TODO。
- **类型一致**：`result_count`/`is_empty`/`subject_id`/`user_type`(P0.1) 贯穿 P1/P2/P4/P5；`prompt_version`(P0.3) 贯穿 P6.2；`needs_review`(P3) 复用进 P2 风险筛选。
- **取舍**：工单只读（外部状态真源）、多副本不实做、result_count 用 helper 推断——均已在抬头说明。
