# TevauAI 客服 — 统一管理后台 设计文档（增量蓝图）

- 日期：2026-05-29
- 范围：在现有 staff 工作台 + admin Prompt 管理基础上，**补齐管理/运营侧全部功能**，做成一个统一后台，按角色分模块。
- 决策结论：六大功能域**全部做**；P0/P1/P2 仅作为实施顺序，不缩减范围。

---

## 1. 背景与定位

现有系统已经是一个**功能完整的一线客服工作台 MVP**：会话接管/转派、AI 草稿审核、留痕回看、工单列表、KPI 看板、知识缺口报表(insights)、工具审计、旁观(spectate)，以及一个 admin Prompt 灰度页。

本设计**不重做这些**，而是在其之上补齐"管理/运营侧"，并把分散的能力收拢进一个统一后台。

两个入口、同一套登录体系（现有 JWT）：

- **工作台**（已有，保留）：一线客服干活 —— 接管、回消息、审 AI 草稿、留痕。
- **管理后台**（本设计）：主管/运营、工程/技术运营、管理层 —— 管人、质检、调 AI、看大盘。

设计原则：
- **复用优先**：现有表/路由/鉴权能复用就复用，新增控制在必要范围。
- **低成本高价值优先**：很多功能"现有数据已具备、只差管理界面"，这类排 P0。
- **每个写操作可审计**：后台所有写操作进统一审计中心。

---

## 2. 现状盘点（复用基线）

已核实的真实结构，作为本设计的复用基线。

### 2.1 数据表（`server/src/ai_engine/persistence/schema.py`）

| 表 | 关键字段 | 复用点 |
|---|---|---|
| `conversations` | user_type(c/b/g), mode(ai/human_takeover/ai_draft), assigned_staff_id, needs_review, archived | 会话检索、质检、大盘 |
| `messages` | role, content, status(done/processing/failed), error_code, topic_verdict, prompt_version, client_message_id | 检索、A/B、失败统计 |
| `staff` | staff_id(唯一), display_name, role(agent/senior/engineer/admin), password_hash, active | 账号管理基线 |
| `tool_audits` | tool_name, params_json, result_size, duration_ms, rejected, reject_reason, result_count, is_empty | 工具健康、审计中心 |
| `attachments` | uploader_type(c/b/staff), object_key, mime, sha256 | 会话详情/质检取证 |
| `tickets` / `ticket_events` | external_id, current_severity, payload_json / event, actor, comment | 工单详情页 |
| `staff_actions` | conversation_id, staff_id, action, at | 绩效、审计中心 |
| `message_feedback` | rating(up/down), reason | 对 AI 的反馈、大盘 |
| `prompt_changes` | actor, old_json, new_json | Prompt 变更审计 |
| `daily_token_usage` | subject_id, user_type, date, input_tokens, output_tokens | 成本大盘基线（**缺 model 维度**） |

### 2.2 鉴权与角色

- JWT（HS256），`server/src/ai_engine/auth/staff_session.py`，claims：`{typ:"staff", sub:staff_id, role, exp(+8h)}`。
- `require_staff` 依赖注入；admin 路由用 `require_admin`（`role=="admin"` 才放行）。
- 路由前缀约定：一线 `/staff/api/v1/...`，管理 `/admin/api/v1/...`。
- 现有角色四级：`agent / senior / engineer / admin`（`staff.role` 有 CheckConstraint 约束）。

### 2.3 前端

- `web/src/routes/staff/*`：9 个一线页面。
- `web/src/routes/admin/PromptsRoute.tsx`：唯一 admin 页。
- `web/src/api/staff.ts` / `admin.ts` / `staffFetch.ts`（Token 注入 + 401 登出）。
- `web/src/hooks/useStaffSession.ts`：JWT 状态管理；`web/src/i18n/index.ts`：多语言（新页面需走 i18n）。

---

## 3. 角色与权限模型（前置改动）

现有四角色覆盖不了"主管/运营、管理层"两类管理后台使用者。**新增两个角色**，把 `staff.role` 的 CheckConstraint 扩展为六个：

| 角色 | 定位 | 管理后台可见模块 |
|---|---|---|
| `agent` | 一线客服 | （仅工作台） |
| `senior` | 高级客服 | 工作台 + 旁观 |
| `supervisor` | **新增** 客服主管/运营 | 坐席组织、会话质检、绩效 SLA、知识库、大盘（只读成本） |
| `engineer` | 工程/技术运营 | AI 运营全部、工具权限、审计中心、系统配置 |
| `manager` | **新增** 管理层 | 数据大盘 + 成本（只读），无写权限 |
| `admin` | 超管 | 全部，含 RBAC/账号/系统 |

权限实现方式（务实路线，避免一上来做重 RBAC 引擎）：

- 阶段一：模块级 gate 用角色判断（沿用 `require_admin` 模式，新增 `require_roles({...})` 依赖）。
- 阶段二（RBAC 域，见 §4.6）：引入 `role_permissions` 表做细粒度权限位，前端菜单按权限位渲染。完整动态 RBAC 列 P2。

---

## 4. 信息架构（统一后台菜单树）

```
管理后台（按角色显示）
├── 概览
│   └── 数据大盘（首页，整合现有 insights/kpi）        [supervisor/engineer/manager/admin]
├── 坐席与组织
│   ├── 客服账号                                       [supervisor/admin]
│   ├── 分组与技能标签                                 [supervisor/admin]
│   ├── 在线状态与排班                                 [supervisor/admin]
│   └── 会话路由规则                                   [supervisor/admin]
├── 会话与质检
│   ├── 全量会话检索                                   [supervisor/engineer/admin]
│   ├── 会话质检（抽检/评分卡/打标）                   [supervisor/admin]
│   ├── 客服满意度                                     [supervisor/manager/admin]
│   └── 工单（列表已有 + 详情页）                      [supervisor/engineer/admin]
├── 绩效与 SLA
│   ├── KPI 看板（已有，增强）                         [supervisor/manager/admin]
│   ├── 客服绩效详情                                   [supervisor/admin]
│   └── SLA 配置与告警                                 [supervisor/admin]
├── AI 运营
│   ├── Prompt 灰度 + A/B（已有）                      [engineer/admin]
│   ├── Prompt 在线编辑与发布                          [engineer/admin]
│   ├── AI 工具权限矩阵                                [engineer/admin]
│   ├── 工具健康度（已有 insights）                    [engineer/admin]
│   ├── 知识库管理                                     [supervisor/engineer/admin]
│   └── 范围与拦截配置                                 [engineer/admin]
├── 成本
│   └── Token 成本大盘                                 [engineer/manager/admin]
├── 报表
│   └── 自定义报表与导出                               [supervisor/manager/admin]
└── 系统
    ├── 统一审计中心                                   [engineer/admin]
    └── 角色与权限（RBAC）                             [admin]
```

---

## 5. 功能域详细设计

每个功能给出：目标 / 使用者 / 复用数据 / 新增数据 / 新增 API / 前端页面 / 优先级。

### 5.1 坐席与组织管理（supervisor/admin）

**a) 客服账号 CRUD** — P0
- 目标：建/停用账号、改角色、重置密码、查最近登录。
- 复用：`staff` 表（含 password_hash PBKDF2、active）。
- 新增字段（`staff`）：`email`、`phone`、`group_id`(FK staff_groups)、`last_login_at`。
- 新增 API：`GET/POST /admin/api/v1/staff`、`PATCH /admin/api/v1/staff/{id}`（改角色/停用）、`POST /admin/api/v1/staff/{id}/reset-password`。
- 前端：`routes/admin/StaffAccountsRoute.tsx`。

**b) 分组与技能标签** — P2
- 目标：按业务线（C端/B端/证券）给客服打标签，供路由用。
- 新增表：`staff_groups(id, name, description, created_at)`；技能标签存 `staff.skills`(JSON 文本列) 或多对多 `staff_group_members`。建议先用 `staff.skills` JSON，简单。
- 新增 API：分组 CRUD `/admin/api/v1/staff-groups`。
- 前端：`routes/admin/StaffGroupsRoute.tsx`。

**c) 在线状态与排班** — P2
- 目标：上线/离线/小休、排班表、当前在岗人数。
- 新增表：`staff_presence(staff_id PK, status[online/away/offline], updated_at)`；`staff_shifts(id, staff_id, start_at, end_at, created_at)`。
- 在线状态更新：工作台心跳 `POST /staff/api/v1/presence`；后台只读聚合。
- 新增 API：`GET /admin/api/v1/presence`、排班 CRUD `/admin/api/v1/shifts`。
- 前端：`routes/admin/PresenceRoute.tsx`、`ShiftsRoute.tsx`。

**d) 会话路由规则** — P2
- 目标：按技能/范围把新会话/转人工会话分到对应组，替代"所有人共享一个队列"。
- 新增表：`routing_rules(id, match_type[user_type/scope/keyword], match_value, target_group_id, priority, active, created_at)`。
- 落地点：现有"转人工/needs_review"入队逻辑读取规则决定 target_group；本设计只定义配置面，路由执行在工作台队列侧接入。
- 前端：`routes/admin/RoutingRulesRoute.tsx`。

### 5.2 会话检索与质检（supervisor/engineer/admin）

**a) 全量会话检索** — P0
- 目标：跨时间/客服/user_type/标签/关键词检索历史会话（现有列表偏"当下队列"）。
- 复用：`conversations` + `messages`。
- 新增：检索索引（PG 上对 messages.content 做 GIN 全文索引或 trigram；SQLite 测试退化为 LIKE，注意两库差异，见已知约束）。
- 新增 API：`GET /admin/api/v1/conversations/search?from&to&staff_id&user_type&q&tag&page`。
- 前端：`routes/admin/ConversationSearchRoute.tsx`，复用现有留痕详情页跳转。

**b) 会话质检** — P1
- 目标：抽检会话、按评分卡打分、打标（违规/优秀/待改进）。
- 新增表：
  - `qa_scorecards(id, name, items_json, active, created_at)` — 评分卡模板。
  - `qa_reviews(id, conversation_id, reviewer_staff_id, scorecard_id, score, items_result_json, tags, comment, created_at)`。
- 新增 API：评分卡 CRUD `/admin/api/v1/qa/scorecards`；质检提交 `POST /admin/api/v1/qa/reviews`；查询 `GET /admin/api/v1/qa/reviews`。
- 前端：`routes/admin/QaReviewRoute.tsx`（取一通会话 + 评分卡打分）。

**c) 客服满意度** — P1
- 目标：会话结束后用户对**人工客服**评分（区别于现有对 AI 的 👍👎 `message_feedback`）。
- 新增表：`agent_ratings(id, conversation_id, staff_id, subject_id, user_type, rating[1-5], comment, created_at)`。
- 采集点：人工会话 resolve 后，C/B 端弹评分（前端工作台 + C 端聊天侧改动）。
- 新增 API：采集 `POST /api/v1/conversations/{id}/agent-rating`；后台聚合 `GET /admin/api/v1/agent-ratings`。
- 前端：后台并入"客服绩效详情"；采集 UI 在 C 端聊天结束态。

**d) 工单详情页** — P0
- 目标：现仅列表，补详情：工单字段 + `ticket_events` 事件链 + 关联会话跳转。
- 复用：`tickets` + `ticket_events`，无新表。
- 新增 API：`GET /admin/api/v1/tickets/{external_id}`（含 events）。
- 前端：`routes/admin/TicketDetailRoute.tsx`。

### 5.3 绩效与 SLA（supervisor/manager/admin）

**a) KPI 看板增强** — 已有，保留。复用 `staff_metrics.py` / `staff_kpi.py`。

**b) 客服绩效详情** — P1
- 目标：下钻到个人：接管量/解决率/平均接管时长/平均解决时长/满意度(`agent_ratings`)/质检均分(`qa_reviews`)趋势。
- 复用：`staff_actions`（take/release/transfer_out/resolved）+ 时间戳算时长；`agent_ratings` + `qa_reviews`。
- 新增 API：`GET /admin/api/v1/staff/{id}/performance?from&to`。
- 前端：`routes/admin/StaffPerformanceRoute.tsx`。

**c) SLA 配置与告警** — P0
- 目标：设接管时长/解决时长阈值，超时告警 + 列表高亮。
- 新增表：`sla_policies(id, metric[take_time/resolve_time], threshold_seconds, scope[user_type/group/all], scope_value, active, created_at)`。
- 违规判定：运行时按 `staff_actions` 时间差计算（不落 breach 表，避免冗余）；告警通过现有事件/SSE 或后台轮询高亮。
- 新增 API：SLA 配置 CRUD `/admin/api/v1/sla/policies`；当前违规 `GET /admin/api/v1/sla/breaches`。
- 前端：`routes/admin/SlaRoute.tsx`。

### 5.4 AI 运营与质量（engineer/admin）

**a) Prompt 灰度 + A/B** — 已有（`admin_prompts.py` + `PromptsRoute.tsx`），保留。

**b) Prompt 在线编辑与发布** — P2（改动较大）
- 现状：Prompt 是文件（`prompts/v1.0.0/`、`v1.1.0/`），改了要 docker 重新构建。
- 目标：在线编辑、版本 diff、发布流（草稿→灰度→全量），减少"改文件+重建"。
- 新增表：`prompt_drafts(id, version, file_name, content, status[draft/published], editor, created_at)`。
- 关键约束：需决定 prompt 真值来源 —— DB 优先还是文件优先（涉及现有 `registry.py`/`loader.py` 加载逻辑改造，及"双版本 v1.0.0/v1.1.0 都要改"的现有约定）。这是本域最重的一项，单独成里程碑。
- 新增 API：草稿 CRUD `/admin/api/v1/prompts/drafts`、`POST .../publish`。
- 前端：`routes/admin/PromptEditorRoute.tsx`。

**c) AI 工具权限矩阵** — P1
- 现状：工具白名单写死在代码（客服代查仅限特定工具；脱敏按角色解锁）。
- 目标：可视化配置"哪个角色能用哪个工具 + 脱敏级别"。
- 新增表：`tool_policies(id, tool_name, role, enabled, redaction_level, updated_by, updated_at)`。
- 落地点：工具执行前置校验从代码常量改读 `tool_policies`（带内存缓存 + 热加载）。
- 新增 API：`GET/PUT /admin/api/v1/tool-policies`。
- 前端：`routes/admin/ToolPoliciesRoute.tsx`（工具 × 角色矩阵）。

**d) 工具健康度** — 已有（`insights.py` tool-health），保留，整合进 AI 运营菜单。

**e) 知识库管理** — P2
- 目标：维护 `lookup_api_doc` / `lookup_error_code` 数据源 + FAQ；把 insights 的"知识缺口"一键转知识条目。
- 新增表：`knowledge_entries(id, type[api_doc/error_code/faq], key, title, content, locale, status[draft/published], source_gap_signal, created_by, updated_at)`。
- 落地点：`lookup_*` 工具优先读 `knowledge_entries`（published），回退现有数据源。
- 新增 API：知识条目 CRUD `/admin/api/v1/knowledge`；缺口转条目 `POST /admin/api/v1/knowledge/from-gap`。
- 前端：`routes/admin/KnowledgeRoute.tsx`，与现有 `InsightsRoute` 缺口列表联动。

**f) 范围与拦截配置** — P2
- 目标：黑名单（subject_id）、敏感词、业务范围开关（如证券范围）可配置。
- 新增表：`guardrail_rules(id, type[blocklist/sensitive_word/scope_toggle], pattern_or_scope, action[block/flag], active, created_by, created_at)`。
- 落地点：chat 入口前置校验读取规则。
- 新增 API：`GET/POST/DELETE /admin/api/v1/guardrails`。
- 前端：`routes/admin/GuardrailsRoute.tsx`。

### 5.5 数据大盘与成本

**a) 核心指标大盘（后台首页）** — P0
- 目标：把分散的 insights/kpi 整合成首页大盘：转人工率、AI 解决率、满意度（AI 反馈 + 客服满意度）、会话量趋势、待复核量。
- 复用：`conversations`、`messages`、`message_feedback`、`staff_actions`、`agent_ratings`。
- 性能：高频聚合考虑日聚合表 `daily_metrics(date, metric, dim, value)`（定时任务回填）；首版可直接查询，量大再加。
- 新增 API：`GET /admin/api/v1/dashboard/overview?from&to`。
- 前端：`routes/admin/DashboardRoute.tsx`（后台首页）。

**b) Token 成本大盘** — P1
- 现状：`daily_token_usage` 有 subject/user_type/date/in/out，**无 model 维度**，无单价换算。
- 目标：按 model / user_type / 时间看 token 量与估算成本。
- 新增：`daily_token_usage` 增列 `model`（改主键为 subject_id+user_type+date+model）；新增单价配置 `model_pricing(model, input_price, output_price, currency, updated_at)`。
- 新增 API：`GET /admin/api/v1/cost/usage?from&to&group_by`。
- 前端：`routes/admin/CostRoute.tsx`。

**c) 自定义报表与导出** — P2
- 目标：选维度/筛选出报表，导 CSV。
- 新增表：`report_definitions(id, name, dims_json, filters_json, owner, created_at)`。
- 新增 API：`GET/POST /admin/api/v1/reports`、`GET .../{id}/export.csv`。
- 前端：`routes/admin/ReportsRoute.tsx`。

### 5.6 系统与安全

**a) 统一审计中心** — P0
- 目标：把 `staff_actions` + `prompt_changes` + `tool_audits` + 后台所有写操作，收拢成一个可检索的操作审计页。
- 新增表：`admin_audit_log(id, actor, action, target_type, target_id, detail_json, created_at)` —— 后台所有写操作统一落这张表（账号变更、SLA 改动、工具策略、知识库、guardrail 等）。
- 实现：封装一个 `audit(actor, action, target, detail)` helper，在所有 admin 写 API 调用。
- 新增 API：`GET /admin/api/v1/audit?actor&action&target_type&from&to&page`（聚合视图，可选合并展示三张历史表）。
- 前端：`routes/admin/AuditCenterRoute.tsx`。

**b) 角色与权限（RBAC）** — P1（基础）/ P2（完整动态）
- 目标：可视化看/调角色权限。
- 阶段一（P1）：展示六角色 × 模块权限矩阵（只读 + 切换 staff 角色，复用账号管理）。
- 阶段二（P2）：`role_permissions(role, permission_key, allowed)` 表驱动菜单与 API gate，支持自定义。
- 新增 API：`GET/PUT /admin/api/v1/rbac/role-permissions`。
- 前端：`routes/admin/RbacRoute.tsx`。

---

## 6. 数据模型增量汇总

新增表：
- 坐席组织：`staff_groups`、`staff_presence`、`staff_shifts`、`routing_rules`
- 质检：`qa_scorecards`、`qa_reviews`、`agent_ratings`
- SLA：`sla_policies`
- AI 运营：`prompt_drafts`、`tool_policies`、`knowledge_entries`、`guardrail_rules`
- 成本/报表：`model_pricing`、`report_definitions`、（可选）`daily_metrics`
- 系统：`admin_audit_log`、（P2）`role_permissions`

修改表：
- `staff` 增列：`email`、`phone`、`group_id`、`skills`(JSON)、`last_login_at`
- `daily_token_usage` 增列：`model`（并入主键）
- `staff.role` CheckConstraint 扩展：加 `supervisor`、`manager`

迁移注意（项目既有约束）：
- 自有库测试跑 SQLite、生产跑 Postgres(asyncpg)，`(:p IS NULL OR ...)` 类型歧义等 Postgres-only bug 会漏过测试 —— 新 SQL 用 `CAST(:p AS TEXT)`，改完必须重建 PG 验真实库。
- 全文检索在 PG/SQLite 行为不一致，检索功能需双库分别验证。

---

## 7. API 增量汇总（前缀 `/admin/api/v1`，除采集类）

- 账号：`GET/POST /staff`、`PATCH /staff/{id}`、`POST /staff/{id}/reset-password`、`GET /staff/{id}/performance`
- 组织：`/staff-groups`、`/presence`、`/shifts`、`/routing-rules`（采集 `POST /staff/api/v1/presence`）
- 会话质检：`GET /conversations/search`、`/qa/scorecards`、`/qa/reviews`、`GET /agent-ratings`、`GET /tickets/{external_id}`（采集 `POST /api/v1/conversations/{id}/agent-rating`）
- SLA：`/sla/policies`、`GET /sla/breaches`
- AI 运营：`/prompts/drafts`、`POST /prompts/drafts/publish`、`/tool-policies`、`/knowledge`、`POST /knowledge/from-gap`、`/guardrails`
- 大盘/成本/报表：`GET /dashboard/overview`、`GET /cost/usage`、`/reports`、`GET /reports/{id}/export.csv`
- 系统：`GET /audit`、`/rbac/role-permissions`

所有写 API 统一调 `audit()` 落 `admin_audit_log`；所有 API 经 `require_roles({...})` 角色 gate。

---

## 8. 落地优先级与里程碑

**M1 — P0（数据已具备、只差界面，最快见效）**
客服账号 CRUD、工单详情页、SLA 配置+告警、核心指标大盘整合、统一审计中心。
（前置：角色体系扩展 supervisor/manager + `require_roles` 依赖 + 后台壳/菜单/路由框架。）

**M2 — P1**
会话质检、客服满意度采集+展示、客服绩效详情、AI 工具权限矩阵、Token 成本大盘、RBAC 基础矩阵。

**M3 — P2**
分组/技能/在线状态/排班/路由规则、Prompt 在线编辑与发布、知识库管理、范围与拦截配置、自定义报表、RBAC 完整动态化。

---

## 9. 非功能性要求

- **鉴权**：复用 JWT；新增 `require_roles()` 依赖；前端菜单按角色/权限位渲染，后端二次校验（前端隐藏≠后端放行）。
- **审计**：后台每个写操作落 `admin_audit_log`。
- **脱敏**：管理后台同样受现有脱敏规则约束（senior 看脱敏、engineer 可解锁）；质检/检索展示原文需走相应角色权限。
- **国际化**：所有新页面文案走 `web/src/i18n`。
- **跨端同步**：采集类改动（presence 心跳、agent-rating、guardrail/knowledge 影响 chat）涉及 C 端聊天与一线工作台，需同步；详见各功能"落地点"。
- **部署**：改后端/prompt 必须 `docker compose up -d --build api` 才生效（restart 不够）。

---

## 10. 假设与未决问题

1. **角色方案**：采用"新增 supervisor/manager 两角色"而非一上来做动态 RBAC。若你们倾向纯权限位模型，M1 角色前置需调整。
2. **Prompt 真值来源**：在线编辑落地需定 DB-first 还是 file-first，影响 `registry.py`/`loader.py` 改造幅度 —— 留到 M3 该任务的子设计再定。
3. **路由规则执行侧**：本设计只覆盖"配置面 + 数据模型"，队列分配执行逻辑接入点需在工作台侧确认。
4. **成本单价**：`model_pricing` 需要业务侧提供各 model 单价；缺单价时大盘只展示 token 量。
5. **大盘性能**：首版直查，若数据量导致慢，再引入 `daily_metrics` 定时聚合。
