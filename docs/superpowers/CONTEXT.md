# Tevau 客服工单 AI 引擎 — 项目摘要

> 子 agent 启动前**先读这份文档**拿全项目上下文。**~200 行紧凑摘要**，详细设计见 [`specs/`](./specs/)，执行任务见 [`plans/mvp-1/`](./plans/mvp-1/) / [`plans/2026-05-19-MVP-2*.md`](./plans/) / [`plans/2026-05-19-MVP-3*.md`](./plans/)。

## 一句话定位

**给客户用的 Claude**：把开发者用 Claude 看代码、查数据库的体验，包装成一个专门答 Tevau Open API/APP 问题的对话框，工具受限、身份隔离、可审计。

## 业务背景

- **公司**：Tevau —— 提供卡片相关 Open API 给合作伙伴，同时有面向终端用户的 APP
- **两类用户**：
  - **C 端 APP 用户**（如普通持卡人）→ 在 APP 内点"客服"→ webview 打开本系统
  - **B 端 BU 合作伙伴**（如 `BU00243780`，调 Open API 的企业客户）→ 浏览器登录本系统
- **当前痛点**：B 端走 `tevau.io/ticket/submit.html` 表单 → Lark 群人工处理，字段经常空着；C 端走 tawk.to 第三方客服聊天，不能"读代码+查数据"

## 核心架构

```
两端用户 → 同一对话前端（React + TS）
              ↓ SSE / HTTPS
        AI 引擎后端（FastAPI + Anthropic SDK）
              ↓ 工具白名单调度（强制身份注入）
   ┌──────────┼──────────┬─────────────┐
代码索引       业务只读库      事项中心 webhook
(Sourcegraph) (MySQL)         (出+回调)
3 个仓库      unlimitpay/      ↓
              nexus 等        事项中心（外部，分派/SLA/CTO 升级）
```

## 关键边界（容易出错的地方）

| 系统 | 职责 | 不做什么 |
|---|---|---|
| **AI 引擎** | 对话、判断、查证、建工单、回应 | 不做分派 / SLA 计时 / 升级 |
| **事项中心**（外部，2026-05 立项 1 周内开工） | 工单分派轮值、SLA 计时、升级到 CTO | 不做 AI 判断 |
| **客服**（2 名 APP 客服）| C 端用户介入 | 不处理 B 端 BU 问题 |
| **技术对接**（嘉豪 + 另一对接人） | B 端 BU 转人工 + 所有 bug 工单 | 不接 C 端用户对话 |
| **tawk.to** | 老 APP 版本继续用 | 不互通新系统聊天历史 |

## 工具白名单（spec §5）

11 个工具：

- 代码：`search_code(repo, query)` / `read_file(repo, path)` — Sourcegraph GraphQL
- 文档：`lookup_api_doc(query)` — 读 Apifox 导出 OpenAPI 3.0 JSON
- 数据（5 个）：`query_user / card / api_call / bu / user_orders / risk_events` — 工具内置 SQL、参数化、**工具层脱敏**
- 工单：`create_ticket(category, summary, evidence, severity)` / `query_ticket_status(id)` — **AI 不指定分派人**

**安全约束**：
- 强制 `tool_router` 注入身份（C=user_id / B=bu_id）
- 服务端二次校验：AI 写其他 ID 直接拒绝
- 所有调用全量审计（≥180 天）
- 工具层脱敏：手机/身份证/卡号/邮箱/规则名

## 问题分类（spec §6.1）—— 5 类

| 类型 | AI 行为 | 建单 |
|---|---|---|
| 无信息 | 追问补字段 | 否 |
| CQ（咨询） | 当场答 + 引用代码/文档 | 否 |
| 事务 | 查数据诊断；需改数据 → 建单 | 是 |
| bug | 收证据 → 建单（强制分给 engineer） | 是 |
| 人工介入 | 用户点"转人工"或 AI 判断 → 建单（C 端给 agent，B 端给 engineer） | 是 |

**两端输出风格**：
- C 端：自然语言、不显代码、不显内部规则名
- B 端：可显技术细节（`file:line`、错误码）
- 共同红线：内部风控规则名（R-xxx）、手机/身份证/全卡号原文 严禁泄露

## 工单状态机（spec §7）

```
[未创建] → AI create_ticket → [created] →（事项中心分派）
   → [assigned] →（受理人开工）→ [in_progress]
       ↓ 解决                ↓ 超时 SLA1
   [resolved]                [escalated → 下一接收人]
       ↓ 用户确认 / 超时         ↓ 超时 SLA2
   [closed]                  [escalated → CTO]
       ↑ 用户拒绝（reopen）     ↓
       └─────────────────────────────┘ 解决回到 resolved
```

SLA 数值表（事项中心配置）：

- p0 = 1h / p1 = 5h / p2 = 24h / p3 = 72h（SLA1）
- SLA2 默认 SLA1 × 2

## 已确定项摘要（spec §12.5）

1. 事项中心 2026-05 已立项，1 周内开工
2. Anthropic 预算先不设限，默认 `claude-sonnet-4-6`
3. 客服 2 名（agent）服务 C 端；嘉豪+另一对接人（engineer）服务 B 端；客服账号独立新建
4. SLA 数值表（见上）
5. B 端身份接受简化方案：输入主账户 ID + DB 校验 + session cookie（受众限定已签约 BU，半公开 ID 可接受）
6. C 端 APP 透传协议：APP JS Bridge 注入 JWT（不进 URL/日志）
7. tawk.to 不迁移、并存期 6-12 个月、客服双系统巡查
8. 数据脱敏：MVP-1 按 spec §5.4 默认（手机/身份证/卡号/邮箱/规则名）
9. engineer role 看原始数据（不脱敏）+ 强制审计
10. 业务库直连阿里云 RDS 只读账号（不走副本）
11. 代码索引：Sourcegraph 自部署（不走 ripgrep 折中）
12. 仓库同步：每日定时 pull
13. Lark 兜底：复用现"Open Api 问题工单通知群"机器人
14. 事项中心 base URL：MVP-1 用 mock 占位
15. 代码索引技术从 MVP-1 起即 Sourcegraph
16. API 文档：Apifox 项目导出 OpenAPI 3.0 JSON
17. 可观测面板：阿里云 Prometheus + Grafana，4 类视角
18. DB 名 `unlimitpay_test`（之前误写为 nexus_test / tevau_test）
19. 业务库结构：单 RDS 实例 + 内/外网双入口 + 5 个业务库（主：unlimitpay_test，次：nexus_test）
20. 测试库有 sample data 可直接联调
21. 卡 ID = Tevau 内部 ID（不是 BU 外部映射）

## 三阶段 MVP 切片

| MVP | 范围 | 时长 |
|---|---|---|
| **MVP-1**（[plan](./plans/mvp-1/README.md)） | B 端 web 对话页 + Sourcegraph + Apifox + SQLite mock + 客服 A 方案（建人工介入工单走 Lark） | 3-4 周 |
| **MVP-2**（[plan](./plans/2026-05-19-MVP-2-客服工单AI引擎.md)） | C 端 APP 接入 + 真 MySQL + B 端主账户 ID 登录 + 客服 B 方案（工作台 v1）+ 反向 webhook | 3-4 周 |
| **MVP-3**（[plan](./plans/2026-05-19-MVP-3-客服工单AI引擎.md)） | 事项中心真接 + self-check 强制 + 客服 C 方案（AI 草稿/旁观/工具代查/KPI）+ 治理 + 可观测 | 3-4 周 |

## 关键决策"为什么"

| 决策 | 为什么 |
|---|---|
| AI 引擎 ≠ 工单系统 | 录音原话"不要造工单系统，要做 AI 引擎"。工单状态机划给事项中心 |
| AI 不感知值班/对接人 | 值班表是动态信息，不该让 AI 知道。事项中心配置 `category → role` 分派规则 |
| 客服 / 技术对接分两条线 | 业务上 2 个 APP 客服只接 C 端；嘉豪等 8 人技术值班只接 B 端 + bug |
| 三阶段渐进上 Sourcegraph / 客服工作台 | MVP-1 验证 AI 引擎本体可行；MVP-2 接真用户；MVP-3 上线全功能 |
| 主账户 ID 简化登录方案 | 受众是已签约 BU 的技术对接人，BU_ID 在合同/Lark/API 文档里多次出现，半公开 ID 可接受 |
| C 端走 APP JS Bridge 而非 URL token | token 不进浏览器历史、不进服务器日志，更安全 |
| 工具层脱敏（不靠 LLM 自觉） | LLM 看到原文就有泄露风险；脱敏在 handler 内做让 LLM 永远看不到 |
| MVP-1 SQLite + mock，MVP-2 才接真 MySQL | 验证引擎逻辑不依赖真 DB；接真库前需要后端给 schema、配只读账号、对齐脱敏字段 |

## 项目布局

```
tevau-cs-engine/                  ← 顶层（共用：README / Makefile / pre-commit / CI / docs / .gitignore）
├── server/                       ← 后端独立子项目
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/ai_engine/
│   └── tests/
├── web/                          ← 前端独立子项目（Vite + React）
│   ├── package.json
│   ├── src/
│   └── tests/
└── docs/                         ← 共用设计与计划文档
```

**命令约定**：后端命令默认在 `server/` 下跑（`cd server && pytest …`）；前端命令默认在 `web/` 下跑（`cd web && pnpm …`）。顶层 `Makefile` 提供聚合 target（如 `make test` = `make -C server test`，`make web-test` = `cd web && pnpm test`）。pre-commit / gitleaks / GitLab CI 都跑在仓库根，但 hook/job 内部按需 `cd server` 或 `cd web`。

## 工程规范基线

- **后端**：ruff strict + mypy strict + pytest 覆盖率 ≥ 75%
- **前端**：eslint + prettier + tsc --noEmit + vitest v8 coverage ≥ 75%
- **pre-commit**：ruff / mypy / gitleaks / detect-private-key / conventional commit msg / 前端 lint+typecheck
- **CI**：GitLab CI 跑 py-lint / py-typecheck / py-test / web-lint / web-test
- **架构约束**：禁止自由 SQL / 禁止绕过 tool_router / prompt 不硬编码人名规则名 / 单文件 ≤ 300 行 / 函数 ≤ 80 行 / 复杂度 ≤ 10
- 详见 [`plans/mvp-1/task-00-engineering-baseline.md`](./plans/mvp-1/task-00-engineering-baseline.md) 和项目根 `CONTRIBUTING.md`

## 阅读地图

| 想知道 | 看哪里 |
|---|---|
| 整体设计与决策 | [`specs/2026-05-18-客服工单AI引擎-design.md`](./specs/2026-05-18-客服工单AI引擎-design.md) |
| 待用户决策项 | spec §12.1 |
| 已确定项与理由 | spec §12.5 |
| 客服流程 | spec §13 + MVP-2/3 plan 对应 task |
| 工程约束 | [`plans/mvp-1/task-00-engineering-baseline.md`](./plans/mvp-1/task-00-engineering-baseline.md) |
| 当前执行 task | [`plans/mvp-1/README.md`](./plans/mvp-1/README.md) |
| 凭证与外部资源 | [`../resources.md`](../resources.md) |
