# MVP-1 客服工单 AI 引擎 — 实施计划（拆分版索引）

> **本目录是 MVP-1 plan 拆分后的版本**（按 task 切分，便于子 agent 单点读取）。每个 task 独立一个 `task-NN-<slug>.md`。  
> 原合并版（已 deprecated）保留在 `../2026-05-18-MVP-1-客服工单AI引擎.md` 作历史参考；新增/修改请只改本目录。

> **For agentic workers:** 执行某个 task 时，**只读** 该 task 的 `.md` + 本 README + `docs/superpowers/CONTEXT.md`（项目摘要）+ 必要时 `../../specs/2026-05-18-客服工单AI引擎-design.md`。不要读完整旧合并版。

---

## 目标

让 Tevau 的 **B 端 BU 合作伙伴**在网页对话框里向 AI 提问，AI 自主调用代码搜索 + 受限 DB 查询 + 文档检索回答；不能解决时自动建工单并推送到 mock 事项中心（兼 Lark 群兜底通知）。

**架构**：Python FastAPI 后端跑 Claude 4.x agent loop，工具调用走白名单 router 强制注入 BU 身份；React 前端走 SSE 接收流式回复。

**Tech Stack**：

- Python 3.12 / FastAPI / Anthropic Python SDK
- SQLite（引擎自身库 + MVP-1 mock 业务表）
- **Sourcegraph 自部署**（代码搜索，3 个 GitLab test 分支）
- **Apifox 导出 OpenAPI 3.0 JSON**（API 文档检索）
- React 18 + TypeScript + Vite + **Tailwind + shadcn/ui** + react-markdown（接入 Tevau APP 设计系统）
- pytest + respx + testcontainers / vitest + v8 coverage

**范围说明**：本 plan 只覆盖 **MVP-1**。C 端 APP 接入、真 MySQL、客服工作台、事项中心真接等延到 [MVP-2](../2026-05-19-MVP-2-客服工单AI引擎.md) / [MVP-3](../2026-05-19-MVP-3-客服工单AI引擎.md)。

**关联文档**：

- 项目摘要（先读这个）：[../../CONTEXT.md](../../CONTEXT.md)
- spec 设计：[../../specs/2026-05-18-客服工单AI引擎-design.md](../../specs/2026-05-18-客服工单AI引擎-design.md)
- 资源/凭证：[../../../resources.md](../../../resources.md)

---

## Task 清单（按顺序执行）

| # | Task | 关键产出 |
|---|---|---|
| 0 | [工程规范基线](task-00-engineering-baseline.md) | ruff / mypy / pre-commit / CI / commit 规范 / 架构约束 |
| 1 | [项目骨架 + 配置加载](task-01-skeleton.md) | `.env.example` / Makefile / `config.py` |
| 2 | [SQLite 持久层](task-02-persistence.md) | schema + conversations/audit/tickets DAO |
| 3 | [Anthropic 客户端封装](task-03-anthropic-client.md) | prompt cache 标注 + stream API |
| 4 | [search_code + read_file（Sourcegraph）](task-04-search-readfile.md) | Sourcegraph GraphQL 客户端 + 工具 |
| 5 | [工具路由 + cost guard](task-05-tool-router.md) | 身份强制注入 + 调用深度/结果裁剪 |
| 6 | [query_user / card / api_call](task-06-query-tools.md) | SQLite mock fixture + BU 强制隔离 |
| 7 | [lookup_api_doc（OpenAPI）](task-07-lookup-api-doc.md) | 读 Apifox 导出 JSON + 加权检索 |
| 8 | [create_ticket + Lark 兜底](task-08-create-ticket.md) | HMAC 推 mock event center + 失败转 Lark |
| 9 | [Prompt 文件 + loader](task-09-prompts.md) | 5 个 system prompt + ephemeral cache |
| 10 | [Agent runtime](task-10-runtime.md) | agent loop + tool dispatch + 流式输出 |
| 11 | [HTTP API](task-11-api.md) | `/api/v1/chat` SSE + `/tickets/:id/events` 回调 |
| 12 | [React 前端](task-12-frontend.md) | Vite + Tailwind + shadcn/ui + APP 设计系统 + markdown |
| 13 | [E2E MVP-1 验收](task-13-e2e.md) | 两个剧本：bug 诊断建单 + 越权拒绝 |
| 14 | [docker-compose + 部署](task-14-deploy.md) | api + web + sourcegraph 三服务 + 部署文档 |

---

## 已知实现缺口（不是隐藏债务，是 MVP-1 范围内有意延后）

执行任何 task 时**务必同时记住**这 10 条：

1. **MySQL 业务库未接入** — Task 6 的 `query_*` 工具读 SQLite `mock_*` 表。MVP-2 接 `unlimitpay_test` + `nexus_test` 真实 MySQL 时整体重构为 `aiomysql` + 连接池，每个业务库独立连接 URL（见 spec §5.5）。
2. **B 端身份是 `X-BU-ID` header 临时方案** — 仅限内网联调，生产必须替换为"主账户 ID 输入 + DB 校验 + session cookie"（spec §4.1）。MVP-2 切换。
3. **self-check 不强制** — Task 9 的 `self_check.md` 只是 system 文本，LLM 可能跳过。runtime 强制 inject 在 MVP-3 上线（spec §8.3）。
4. **工单状态不实时推前端** — Task 11 写库了，但前端不知道。MVP-1 阶段前端可点"刷新"看；MVP-2 用轮询，MVP-3 升级 SSE（spec §7.5）。
5. **会话长度无硬上限** — MVP-1 不做"轮次/token 上限+自动总结"；MVP-3 上线（spec §11）。
6. **成本治理无硬阈值** — MVP-1 仅有工具调用深度上限；单 BU/单日 token 预算阈值在 MVP-3 加（spec §11）。
7. **数据脱敏未在工具层实施** — MVP-1 阶段 mock 数据本身不敏感；接真实库前必须按 spec §5.4 在每个 `query_*` handler 内做脱敏，并在 LLM 输出层加正则兜底扫描。
8. **HMAC 单 key** — MVP-1 用单 key（`EVENT_CENTER_SECRET`）；事项中心真接入时升级为双 key（`CURRENT`/`PREVIOUS`）热轮换（spec §7.4）。
9. **user_type 未在 SSE 协议里传** — MVP-1 一律 B 端；MVP-2 接入 C 端时在 `conversation` SSE 事件里加 `user_type` 字段（spec §6.2 末段）。
10. **AI 引擎自身库 vs 业务只读库未严格分离** — MVP-1 都在一个 SQLite 文件里（`ai_engine.db`，含 `mock_*` 表）；MVP-2 必须拆成 `aiosqlite://engine.db` + `aiomysql://unlimitpay`（主业务库，走 `tevau_test_read` 只读账号）+ `aiomysql://nexus`（次业务库，待 DBA 配只读账号）多连接。

**执行人请记住**：如果在 MVP-1 task 里发现想"顺手"修复以上任一条 → **不要**。它们是 MVP-2/3 的工作量，MVP-1 落地后单独立项。

---

## 完成标准

- 所有 `pytest` 通过（覆盖 15 个 task 的测试 + 端到端，覆盖率 ≥ 75%）
- 所有 `vitest` 通过（React 前端，覆盖率 lines/functions/statements ≥ 75%，branches ≥ 70%）
- 所有 `pre-commit` hooks 通过（ruff / mypy / gitleaks / prettier / conventional commit）
- 手动验收路径：
  1. 起 Sourcegraph 容器，索引 3 个 GitLab `test` 分支
  2. 从 Apifox 导出 OpenAPI JSON 放到 `repos/api-docs/openapi.json`
  3. `docker compose up` 起后端 + 前端
  4. 浏览器打开 `http://localhost:5173`
  5. 在对话框里输入"BU00243780 的 /v2/card/bind 偶发 500，uid=1765348436409"
  6. 观察 AI 调 `query_api_call` → `search_code` → `create_ticket` 流式输出
  7. 查看 `INBOX` 状态：mock event center 已收到工单
  8. POST 一个签名正确的回调到 `/api/v1/tickets/{external_id}/events`，工单状态变化已落库（MVP-1 不强制展示给用户，MVP-2/3 加）

---

## 未尽事项（流向 MVP-2 / MVP-3）

详见各自 plan：

- [MVP-2 plan](../2026-05-19-MVP-2-客服工单AI引擎.md)：C 端接入 + 真 MySQL + 客服工作台 v1 + 反向 webhook
- [MVP-3 plan](../2026-05-19-MVP-3-客服工单AI引擎.md)：事项中心真接 + self-check + 治理 + 客服 C 方案 + 可观测

待用户/团队后续闭合的事项见 [spec §12.1-12.4](../../specs/2026-05-18-客服工单AI引擎-design.md#12-未决事项需后续对接才能闭合)。
