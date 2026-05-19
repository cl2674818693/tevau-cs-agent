# MVP-2 客服工单 AI 引擎 — 实施计划（拆分版索引）

> **本目录是 MVP-2 plan 按 task 拆分后的版本**（便于子 agent 单点读取）。每个 task 一个 `.md`。  
> 原合并版（已 deprecated）保留在 `../2026-05-19-MVP-2-客服工单AI引擎.md` 作历史参考。

> **For agentic workers:** 执行某个 task 时，**只读** 该 task 的 `.md` + 本 README + `../../CONTEXT.md`（项目摘要）+ 必要时 spec / MVP-1 已落地代码。

---

## 目标

在 MVP-1 基础上：让 C 端 APP 用户能从 APP webview 进来对话；让 B 端 BU 在网页输主账户 ID 登录；把 `query_*` 工具从 SQLite mock 切到真实 MySQL（`unlimitpay_test` + `nexus_test`）；上线**客服工作台 v1**（B 方案接管），打通 AI ↔ 客服 ↔ 用户三方实时对话。

**架构**：沿用 MVP-1 后端，新增 aiomysql 业务库连接池（多库分离）、客服账号系统、客服侧 API + SSE 双向消息、独立客服工作台 SPA。前端引入 React Router 区分 `/`（对话）与 `/staff/`（工作台）。

**Tech Stack**：

- Python 3.12 / FastAPI / Anthropic SDK / aiomysql + asyncmy / aiosqlite（引擎库）/ Sourcegraph
- React 18 + TypeScript + Vite + React Router + Tailwind + shadcn/ui
- pytest + respx + testcontainers[mysql] / vitest + v8 coverage

**前置**：[MVP-1 plan](../mvp-1/README.md) 已实施完毕。

**关联**：[`../../CONTEXT.md`](../../CONTEXT.md) / [`../../specs/2026-05-18-客服工单AI引擎-design.md`](../../specs/2026-05-18-客服工单AI引擎-design.md)

---

## 已知实现缺口（MVP-2 范围内有意延后）

1. **事项中心仍是 mock** — 真接放 MVP-3（事项中心 2026-05 立项 1 周内开工）
2. **客服工作台是 B 方案**（接管+释放+收发消息）— C 方案的 AI 辅助/草稿模式/多客服协作在 MVP-3
3. **HMAC 单 key** — 事项中心真接入时升级双 key（MVP-3）
4. **会话长度无硬上限** — MVP-3 加自动总结+开新会话
5. **成本治理无单 BU/单 user 硬阈值** — MVP-3 加
6. **self-check 不强制 inject** — MVP-3 加
7. **可观测面板未上线** — MVP-3 上 Prometheus + Grafana

---

## Task 清单（按顺序执行）

| # | Task | 关键产出 |
|---|---|---|
| 1 | [aiomysql 业务库连接池](task-01-aiomysql-pool.md) | `BusinessDB` 多库管理 + 2s 慢查询兜底 |
| 2 | [数据脱敏 utils](task-02-redact.md) | mask_phone/id_card/card_no/email + LLM 输出兜底正则 |
| 3 | [query_* 重写：aiomysql 真接](task-03-query-tools-real.md) | 用 testcontainers 起 MySQL 跑真 SQL + 工具层脱敏 |
| 4 | [B 端主账户 ID 登录](task-04-bu-login.md) | session cookie + 速率限制 + 防枚举错误 |
| 5 | [C 端 APP JWT 验签](task-05-c-jwt.md) | pyjwt RS256 + JS Bridge + 两端身份识别 |
| 6 | [C 端 reply_style.c.md prompt](task-06-c-prompt.md) | loader 按 user_type 切换风格 |
| 7 | [conversations.mode + staff 表](task-07-mode-staff-schema.md) | DB 扩展 + DAO + migration script |
| 8 | [客服 JWT + 登录](task-08-staff-auth.md) | staff JWT + 密码 hash + login 端点 |
| 9 | [客服 take/release/messages/stream API](task-09-staff-takeover-api.md) | 原子接管 409 + SSE 订阅总线 |
| 10 | [chat 端点 human_takeover 分支](task-10-chat-human-mode.md) | 跳过 AI agent，用户消息直推客服 |
| 11 | [反向 webhook /user-events + /request-human](task-11-user-events.md) | JWT 身份二次校验 + 同步事项中心 |
| 12 | [事项中心客户端封装](task-12-event-center-client.md) | HMAC 推 closed / reopen / confirmed |
| 13 | [LLM 输出兜底脱敏](task-13-runtime-redact.md) | runtime yield text 前过 scan_and_redact_text |
| 14 | [React 路由 + 三色气泡 + 转人工 + TicketCard 按钮](task-14-frontend-staff-ui.md) | BrowserRouter + human_agent 气泡 + 反向 webhook 触发 |
| 15 | [客服工作台 SPA v1](task-15-staff-console.md) | `/staff/login` + `/staff/conversations` + detail 详情页 |
| 16 | [E2E MVP-2 验收](task-16-e2e.md) | 5 个剧本：C 端 / B 端 / 客服接管 / 越权 / 反向 webhook |
| 17 | [docker-compose 加 MySQL + 部署文档](task-17-deploy.md) | mysql 服务 + seed.sql 自动加载 + 客服账号初始化 |

---

## 完成标准

- 所有 pytest / vitest 通过
- 真实 MySQL 接入：query_user/card/api_call 用 `unlimitpay_test`
- C 端 JS Bridge 可在 APP webview 注入 JWT → AI 用 C 端 prompt 风格答
- B 端"主账户 ID 输入"登录 + session cookie 替换 X-BU-ID
- 客服工作台 v1 可登录、列表、接管、释放、收发消息
- 用户侧 TicketCard 有"已解决/未解决"按钮 → 反向 webhook 工作
- 输出脱敏：手机/身份证/卡号/邮箱/规则名 在工具层 + LLM 输出层双重脱敏

---

## 未尽事项 → [MVP-3](../mvp-3/README.md)

- 事项中心真实对接（替换 mock）+ HMAC 双 key 轮换
- 多轮一致性 self-check 主链路强制 inject
- 会话长度治理（≤ 20 轮 / ≤ 100K token + 自动总结）
- 成本治理硬阈值（单 BU/单 user 单日 token 上限）
- 客服工作台 C 方案（AI 旁观 / 草稿审核 / 工具代查 / 多客服协作 / KPI）
- 工单状态变化 SSE 长连推用户对话（MVP-2 用轮询，MVP-3 升 SSE）
- Prompt 版本化管理面板
- 可观测面板：AI 引擎 `/metrics` → 阿里云 Prometheus → Grafana
