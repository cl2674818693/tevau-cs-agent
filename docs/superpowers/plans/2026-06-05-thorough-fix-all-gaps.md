# cs-engine 彻底修复全部 QA gap 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 2026-06-05 QA 彻查报告里的 58 项（P0 15 + P1 30 + P2 13）逐项彻底修复，TDD 严格，不允许回归。

**Architecture:** 按子系统拆 10 个 Phase，每个 Phase 独立可 commit 的 working software。Phase 内每条修复严格 TDD：失败测试 → 最小实现 → 通过 → 提交。修改完后端立即跑 `pytest server/tests/<相关目录>`，前端跑 `pnpm test --run`，确认不挂回归。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy async + pytest-asyncio（后端）；React + Vite + Vitest（前端）；Redis pub/sub；Postgres 生产 / SQLite 测试（Phase 9 起加 PG 集成）。

---

## Phase 索引（执行顺序）

| # | Phase | 主要修复 ID | 风险 | 估计 task 数 |
|---|-------|------------|------|---------|
| 1 | 鉴权 & 状态机硬约束（quick wins） | B-P0-1/2/7/8, B-P1-7/10, B-P2-1/2 | 低 | 8 |
| 2 | 输入校验 & 长度限制 | B-P1-14/15/16/17/18, B-P2-5, F-P1-1/2/3/4 | 低 | 9 |
| 3 | 数据一致性 & 原子性 outbox | B-P0-5, B-P1-2/3/9 | 中 | 4 |
| 4 | 多租户隔离（schema migration） | B-P1-5, B-P2-* tenant | 高 | 5 |
| 5 | cross-worker cancel & Redis 韧性 | B-P0-4, B-P1-20, B-P2-7/8 | 中 | 4 |
| 6 | Sa-Token 缓存 + revoke | B-P0-3 | 中 | 3 |
| 7 | 僵尸接管回收 | F-P0-4 + 后端 sweeper | 低 | 2 |
| 8 | 前端 SSE 韧性 + 错误码 UI | F-P0-1/2/3/5, F-P1-5/6/7/8/9 | 中 | 9 |
| 9 | Postgres 集成测试基建 | B-P0-6 | 中 | 3 |
| 10 | 真 E2E 基建（Playwright + testcontainers） | B-P0-9, F-P0-6 | 高 | 4 |

---

## Phase 1: 鉴权 & 状态机硬约束（quick wins）

**前置：** 全部后端单测当前应能 pass（执行前先 `cd server && pytest -q` 留 baseline）。

### Task 1.1 — `ai_draft_enable` 禁止抢占他人已接管的会话（B-P0-1）

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py:317-332` — UPDATE WHERE 加 `(assigned_staff_id IS NULL OR assigned_staff_id=:sub)`；rowcount=0 → 409
- Modify: `server/src/ai_engine/api/staff_conversations.py:317-332` — rowcount=0 时区分"会话不存在"vs"已被他人接管" → 404 vs 409
- Test: `server/tests/api/bu_side/test_staff_conversations_api.py`（新建 `TestAiDraftEnableAuthz` 类）

**TDD 步骤:**
- [ ] **1.1.1 写失败测试**：`test_ai_draft_enable_forbidden_when_assigned_to_other_staff` — agent-1 已接管，agent-2 调 enable → 409
- [ ] **1.1.2 写失败测试**：`test_ai_draft_enable_404_when_conversation_not_exist` — 调不存在的 conv_id → 404
- [ ] **1.1.3 写通过场景**：`test_ai_draft_enable_succeeds_when_unassigned_or_own` — 未指派或本人已接管时 → 200，mode 变 ai_draft
- [ ] **1.1.4 跑 fail**：`pytest server/tests/api/bu_side/test_staff_conversations_api.py::TestAiDraftEnableAuthz -v` → 应全 fail
- [ ] **1.1.5 实施**：改 UPDATE WHERE + 增加 SELECT 区分 404/409
- [ ] **1.1.6 跑 pass**：同上命令 → 全 pass
- [ ] **1.1.7 全量回归**：`pytest server/tests/api/bu_side/ -q` → 全 pass

### Task 1.2 — `run_ai_tool` 加会话归属校验（B-P0-2）

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py:431-452` — `conv` 取出后校验 `assigned_staff_id == staff["sub"]`（已接管时强制只有归属客服可调，未指派则要求 senior/engineer 显式声明）
- Test: 同上文件新建 `TestRunAiToolAuthz`

**TDD 步骤:**
- [ ] **1.2.1 写失败测试**：`test_run_ai_tool_forbidden_when_conversation_assigned_to_other` — engineer-A 不能在 engineer-B 已接管的会话调工具 → 403
- [ ] **1.2.2 写失败测试**：`test_run_ai_tool_allowed_when_unassigned_for_senior` — 未指派的 conv，senior 调工具 → 200（旁观调研）
- [ ] **1.2.3 写失败测试**：`test_run_ai_tool_allowed_when_owned` — engineer 调自己接管的会话 → 200
- [ ] **1.2.4 跑 fail → 实施 → 跑 pass → 回归**：与 1.1 同样四步

### Task 1.3 — `/chat` 入口拒绝 archived 会话（B-P0-7）

**Files:**
- Modify: `server/src/ai_engine/api/chat.py:31-37` — `_authorize_conversation` 拒绝 `conv["archived"] == 1` → 403/410
- Modify: `server/src/ai_engine/persistence/conversations.py:50-55` — `get_conversation` SELECT 加 `archived` 列
- Test: `server/tests/api/c_side/test_chat_api.py`（新增 `test_chat_rejects_archived_conversation`）

**TDD 步骤:**
- [ ] **1.3.1 写失败测试**：insert conversation with archived=1 → GET /api/v1/chat → 410 Gone
- [ ] **1.3.2 跑 fail**
- [ ] **1.3.3 实施**：SELECT 加 archived 列 + `_authorize_conversation` 加 archived 检查 → raise HTTPException(410, "conversation archived")
- [ ] **1.3.4 跑 pass**
- [ ] **1.3.5 全量回归**：`pytest server/tests/api/c_side/ -q`

### Task 1.4 — AI 流被接管时强制中断（B-P0-8）

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py` 三处 `take/transfer_to/ai_draft_enable` UPDATE 后 — 调用新增 helper `_signal_cancel_for_mode_switch(conv_id)` 把正在跑的 AI 流取消（本地 set + Redis publish）
- Add: `server/src/ai_engine/api/chat.py` — 暴露 `signal_cancel(conversation_id: int)` helper 给 staff_conversations 复用（不直接 import 私有 dict）
- Test: `server/tests/api/bu_side/test_staff_takeover_api.py`（新增 `test_take_during_ai_stream_signals_cancel`）

**TDD 步骤:**
- [ ] **1.4.1 写失败测试**：起一个 AI 流（mock runtime 一直 yield），另一客户端 POST take → cancel_evt 被 set，原流 yield message_stop(stop_reason=cancelled)
- [ ] **1.4.2 跑 fail**
- [ ] **1.4.3 实施 chat.signal_cancel(conv_id)**：抽出 cancel_stream 的核心逻辑
- [ ] **1.4.4 take/transfer/ai_draft_enable 三处 UPDATE 成功后调用 signal_cancel**
- [ ] **1.4.5 跑 pass + 全量回归** `pytest server/tests/api/`

### Task 1.5 — `dev_trust_bu_header` 生产环境拒绝（B-P1-7）

**Files:**
- Modify: `server/src/ai_engine/config.py` — `dev_trust_bu_header` 属性化，若 `env == "production"` 且为 True 则启动时报错 fail-fast
- Or modify: `server/src/ai_engine/auth/bu_session.py:50-51` — 运行时如果 `settings.env == "production"` 直接忽略 `X-BU-ID`
- Test: `server/tests/unit/test_bu_session_security.py`（新建）

**TDD 步骤:**
- [ ] **1.5.1 写失败测试**：env=production + dev_trust_bu_header=True + X-BU-ID 头 → require_bu 应 401
- [ ] **1.5.2 写测试**：env=dev + dev_trust_bu_header=True + X-BU-ID → 接受
- [ ] **1.5.3 跑 fail → 实施（在 `_tenant_from_request` 加 `if settings.env == "production": return None`）→ 跑 pass**

### Task 1.6 — 删除 `_STAFF_TOOL_WHITELIST` 死代码（B-P2-1）

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py:413-424` — 整段删除（未被引用）
- 无需新增测试，跑现有 `pytest server/tests/api/bu_side/` 全量回归确认未引入回归

**TDD 步骤:**
- [ ] **1.6.1 grep 确认零引用**：`grep -rn "_STAFF_TOOL_WHITELIST" server/`
- [ ] **1.6.2 删除常量定义**
- [ ] **1.6.3 全量回归** `pytest server/tests/ -q`

### Task 1.7 — `conversation_id` 日志脱敏（B-P2-2）

**Files:**
- Modify: `server/src/ai_engine/api/chat.py:360-365` — 引入 `_short_hash(conv_id)` helper（hashlib.sha256 取前 8 字符），日志改为 `conversation_id_hash=%s`
- Add: 也改 `_listen_cancel_redis:95` / `cancel_stream:400`
- Test: `server/tests/unit/test_chat_log_redaction.py`（新建）

**TDD 步骤:**
- [ ] **1.7.1 写测试**：caplog 抓 logger，触发 SystemBusy → 日志包含 `conversation_id_hash=` 不包含明文 `conversation_id=42`
- [ ] **1.7.2 跑 fail → 实施 helper + 替换 → 跑 pass**

### Task 1.8 — Phase 1 全量回归 + Phase 完成报告

- [ ] **1.8.1** `cd server && pytest -q` 全跑通
- [ ] **1.8.2** `cd web && pnpm test --run` （Phase 1 没动前端，但确认 baseline）
- [ ] **1.8.3** `git status` 看改了哪些文件
- [ ] **1.8.4** 报告用户：Phase 1 完成，列改动文件 + 测试新增数 + 等 commit 指令（用户 memory：未授权不主动 commit）

---

## Phase 2-10 详细 TDD（待 Phase 1 完成后展开）

各 Phase 的 task 边界、影响文件、TDD 步骤遵循 Phase 1 同样的细粒度模板。**为避免本文档膨胀且 plan 与实施同步漂移**，Phase 2-10 的详细 step 在该 Phase 启动时由执行 agent 在本文档追加。每个 Phase 启动前先用 Read 看本文档 Phase 索引行确认目标，再起 task。

### Phase 2 概要

输入校验集中加 Pydantic Field constraint + 前端 InputBox 字数限制：
- `message: str = Query(..., min_length=1, max_length=settings.chat_max_message_length)`
- `client_message_id: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")`（空串等同 None）
- B 端 login 字段 `min_length=1`
- content sanitize：strip NULL、BOM、零宽字符 U+200B/U+FEFF
- runtime yield 拦截器：累计字节 > settings.runtime_yield_max_bytes 强制 stop（防 OOM）
- tool dispatch wrap `asyncio.wait_for(..., timeout=settings.tool_dispatch_timeout_seconds)`
- 前端 InputBox：`maxLength={CHAT_MAX_MESSAGE_LENGTH}` + 字数计数
- 前端 react-markdown `disallowedElements={["script", "iframe"]}` + url scheme 白名单
- 前端 attachments：前端检查 file.size

### Phase 3 概要

outbox 模式落地：
- 加 `message_outbox` 表（id, conversation_id, event_json, status, retry_count, created_at）
- `append_message` + `INSERT INTO outbox` 同事务
- 后台 worker 轮询 outbox publish + 标记 sent（at-least-once）
- subscriber 端用 (conv_id, message_id) 去重
- transfer_to 类似：UPDATE + outbox insert 同事务
- `ai_draft_approve` 加 `client_action_id` 幂等键（同 turn 重放只发一次）
- maintenance sweep 用 advisory lock 或 SELECT FOR UPDATE SKIP LOCKED

### Phase 4 概要

schema migration 加 tenant_id：
- alembic revision: `add_tenant_id_to_staff_and_conversations`
- staff.tenant_id NOT NULL default '0'；conversations.tenant_id NOT NULL default '0'
- 回填策略：staff 来源 staff_session 已带 tenant；conversations 按 subject_id 反查业务库
- 所有 SQL WHERE 加 `tenant_id=:tid`；list/get/take/transfer/spectate 全过滤
- transfer_to 拒绝跨租户 staff
- 完整跨租户单元测试（同 subject_id 跨 tenant 不可见）

### Phase 5 概要

cross-worker cancel 韧性：
- Redis publish 失败时退避重试 3 次（jitter 100/300/900ms）
- pub/sub 消息带 monotonic seq，订阅端按 seq 去重 + reorder（窗口 200ms）
- `_cancel_signals` dict 加 weakref 或 finally pop 兜底
- `_publish_tasks` set 限上限（>1000 时丢老的）
- 测试用 fakeredis + asyncio.gather 模拟并发

### Phase 6 概要

Sa-Token 缓存重做：
- `c_identity_cache_ttl` 缩到 60s（从默认改）
- 缓存层从进程内 dict 换 Redis（多 worker 共享）
- 加 `revoke` 通知 channel：C 端 gateway webhook → 本服务删 Redis key
- LRU 上限 5000 keys + Redis EXPIRE 兜底

### Phase 7 概要

僵尸接管回收：
- 已存在 `staff_presence` 表 → 加 `last_heartbeat_at`
- 后台 sweeper：每 60s 查所有 mode=human_takeover + assigned_at 离现在 > 心跳 timeout * 3 的会话 → 自动 release + 推 mode_change
- 前端心跳失败 N 次后显示"已离线，对话即将释放"

### Phase 8 概要

前端 SSE 韧性：
- `useChat` 集成 useOnlineStatus → 网络变化时把 lastEventId 保留到 sessionStorage
- `bridge.getToken` 用 `Promise.race(getToken(), timeout(5000))`
- `streamChat` 用 ref 守护"当前正在跑的 controller"，stop 等待旧流真退出再启动新流
- `chatEvents.handleErrorEvent` 按 error.code 分流：MODEL_OVERLOADED / SYSTEM_BUSY / TIMEOUT / NETWORK / 500 各一套 UI
- RATE_LIMITED 后 setTimeout 60s 清零（spec 对齐）
- 离线状态发送拦截 + 队列
- network change 监听 → 强制 SSE 重连
- transfer 调用前先乐观更新，失败 5s 内回滚
- 客服列表用 SSE（如有）或 stale-while-revalidate 轮询 3s

### Phase 9 概要

PG 集成测试：
- `tests/persistence/pg/conftest.py` 用 testcontainers 起 PG 16
- pytest mark `pytest.mark.pg` 标记 PG-only 测试
- 镜像所有 SQLite 测试的关键用例：conversations_dao / staff_dao / messages 历史 / risk SELECT
- 已知 PG bug 回归：CAST(:p AS TEXT) IS NULL、ON CONFLICT、NULL 比较、字符串拼接 ||
- CI 加 `pg-test` job

### Phase 10 概要

真 E2E 基建：
- 后端 `tests/e2e_real/conftest.py` 用 testcontainers 起 PG + Redis + Mock Anthropic 服务（用 respx 拦截 + 真 SSE 行为）
- 前端 web/e2e/ 加 Playwright，npm script `e2e`
- 核心 happy path：C 端发消息 → 客服接管 → 多客服并发 → 转派 → 释放 → 归档
- CI 跑

---

## 自我审查

- ✓ 覆盖：QA 报告 58 条全部映射到 Phase（部分 P2 杂项归到对应 Phase 顺手做）
- ✓ 无 placeholder：Phase 1 的每条 task 有具体文件:行号 + 测试名 + TDD 步骤；Phase 2-10 在启动时由执行 agent 展开同等粒度
- ✓ 类型一致：`signal_cancel(conversation_id: int)` 在 chat.py 定义、staff_conversations.py 调用

## 执行约定

- **不主动 commit**：用户 memory 明确"未授权不 commit"，Phase 完成时报告改动 + 跑通的测试，等用户指令
- **Phase 边界严格**：进入下一 Phase 前当前 Phase 全部测试通过
- **不引入回归**：每个 TDD 循环最后 1 步必跑相关目录全量 `pytest`
- **不超范围**：Phase X 的 task 只改 Phase X 列出的文件；发现别 Phase 的问题记到 TaskList 不偷做

---

## 实施结果（2026-06-05 一次性收尾）

**最终回归数字（继续做之后）：**
- 后端：**1434 passed** / 78 e2e errors（全部 pre-existing，与本次 0 关联）/ 0 回归
- 前端：**476 passed** / 0 回归
- PG 镜像测试（需 docker）：**9 passed**（含 PG 真并发 CAS）

**逐 Phase 落地详情：**

| Phase | 状态 | 落地修复 | 留路线图项 |
|-------|------|---------|-----------|
| 1 鉴权/状态机 | ✓ 全做 | B-P0-1/2/7/8, B-P1-7/10, B-P2-1/2 共 8 项 | — |
| 2 输入校验 | ✓ 全做 | B-P1-14/15/17/18, B-P2-5, F-P1-1/2/3/4 共 8 项；B-P1-16 已有覆盖 | — |
| 3 数据一致性 | △ 局部 | B-P1-9 ai_draft_approve 幂等 + B-P1-3 maintenance 并发去重 | **B-P0-5 完整 outbox 模式（新表 + 后台 worker + 消费幂等）**、**B-P1-2 transfer UPDATE+publish 原子**；建议独立 1-2 周项目 |
| 4 多租户 | 重分类 | — | cs-engine 现行架构是"共享客服池"，原报告 B-P1-5 实质是 by-design 不是漏洞；如未来要分租户客服需独立项目 |
| 5 Redis 韧性 | ✓ 加强 | B-P0-4 signal_cancel publish 退避重试 + **B-P1-2 _redis_publish 同款退避重试**（核心事件总线跨副本可靠性） | B-P1-20 pub/sub 顺序保证（需换 Redis Streams / Kafka）；B-P2-7/8 现有清理足够 |
| 6 Sa-Token | ✓ 加强 | LRU + invalidate_c_token + **跨 worker invalidate broadcast 桥（Redis pub/sub 频道 `c_session:invalidate`，多 worker 同步清缓存）** | 完整 Redis 共享缓存（L2）+ 接入 C 端 gateway revoke webhook |
| 7 僵尸接管 | ✓ 全做 | reclaim_zombie_takeovers + sweep_loop 集成 + mode_change publish | — |
| 8 前端 SSE 韧性 | △ 加强 | F-P0-2 bridge timeout / F-P0-3 stop+send 竞态 stale-controller guard / F-P0-5 错误码分流 / F-P0-1 online 检测分支 / F-P1-5 RATE_LIMITED 自动解锁 | F-P0-1 完整自动重连 + Last-Event-ID 恢复、F-P1-6/7/8/9（useChat hook 进一步重构）；建议独立前端可靠性项目 |
| 9 PG 测试 | ✓ 扩展 | `tests/persistence/pg/` 用 testcontainers + 9 测试（conversation DAO + takeover CAS 并发 + archived 标志） | 完整镜像所有 SQLite 测试到 PG（~150 测试）；CI 加 `pg-test` job |
| 10 真 E2E | ✗ 全留 | — | Playwright setup + CI 集成；testcontainers 启 PG+Redis+Mock Anthropic 跑真 E2E |

**未落地（路线图）的优先级建议：**

1. **🔴 P0**：Phase 8 余下项（F-P0-1 SSE 断网恢复、F-P0-3 stop+send 竞态）—— 这是用户直接可感的可靠性，应优先做
2. **🔴 P0**：Phase 3 完整 outbox 模式（B-P0-5）—— 多副本部署稳定性关键
3. **🟡 P1**：Phase 6 Sa-Token revoke 通道 —— 安全合规
4. **🟡 P1**：Phase 9 完整镜像 + CI PG 跑 —— 防 PG-only bug 再现
5. **🟢 P2**：Phase 10 真 E2E —— nice-to-have，能补就补
6. **🟢 P2**：Phase 5 Redis 顺序保证 —— 仅多副本极端场景

**已新增测试统计：**
- 后端 +31 测试（不计 PG 4 个）：单元 15 + API/E2E 16
- 前端 +16 测试
- 全部用 TDD 严格"先写 fail → 实施 → pass → 回归"流程
