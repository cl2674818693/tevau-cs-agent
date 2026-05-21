# Onboarding — Tevau 客服工单 AI 引擎

> 新成员/新 agent 入门。深入设计见 [`docs/superpowers/CONTEXT.md`](docs/superpowers/CONTEXT.md)（~200 行项目摘要）与 [`docs/superpowers/specs/`](docs/superpowers/specs/)；逐 task 计划见 [`docs/superpowers/plans/`](docs/superpowers/plans/)。

## 一句话定位

**给客户用的 Claude**：把"开发者用 Claude 看代码、查数据库"的体验，包装成专门答 Tevau Open API / APP 问题的对话框——工具受限、身份隔离、可审计。

- **两类用户**：C 端 APP 持卡人（APP webview 打开，Bearer RS256 JWT）+ B 端 BU 合作伙伴（浏览器 cookie / `X-BU-ID` 登录）。
- **职责边界**：AI 引擎只做 *对话 / 判断 / 查证 / 建工单 / 回应*；**分派 / SLA / 升级由外部「事项中心」做**。客服只接 C 端；技术对接（嘉豪等）接 B 端 + 所有 bug 工单。

## 仓库布局

```
server/   后端：Python 3.12 / FastAPI + Anthropic SDK（src/ai_engine/, tests/）
web/      前端：Vite + React 18 + TS + Tailwind + shadcn/ui（src/, tests/）
grafana/  Grafana 面板 JSON + Prometheus 告警规则
infra/    阿里云 Prometheus 抓取配置示例
docs/     设计 spec、分阶段计划、资源清单
docker-compose.yml / Makefile  顶层公用
```

## 跑起来

前置：`uv`（后端）、Node 20 + pnpm（前端）、Docker（跑真实 MySQL 集成测试时）。

```bash
# 后端
make install            # uv pip install -e ".[dev]"
cp server/.env.example server/.env   # 填 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL（公司网关）
make run                # uvicorn --reload :8000

# 前端
make web-install
make web-dev            # :5173   （B 端 /bu/login，客服 /staff/login）

# 一键容器化（含 MySQL / Sourcegraph）
docker compose up --build api web
```

公司自建 Claude 网关：`ANTHROPIC_BASE_URL=https://awsclaude.tevaupay.com` + `ANTHROPIC_API_KEY=<网关 key>`。

## 测试 / 质量门禁

每个改动都过：后端 `ruff` + `mypy --strict` + `pytest`；前端 `tsc` + `eslint` + `vitest`（覆盖率阈值 75/70/75）。

```bash
make check        # 后端：lint + typecheck + test（CI 等价）
make web-test     # 前端 vitest
```

当前状态：**后端 166 测试通过，前端 62 测试通过**，全门禁绿。
- 真实 MySQL 集成测试用 `testcontainers`，无 Docker 时自动 skip。
- 多数 pytest warning 是无害的（FastAPI `on_event` deprecation、测试短 JWT key 长度提示）。

## 进度：MVP-1 / 2 / 3 均已落地

| 阶段 | 内容 |
|---|---|
| **MVP-1** | Agent 循环 + 工具白名单（强制身份注入）+ 脱敏 + 建工单 + SSE + prompt 系统 |
| **MVP-2** | 业务只读库（MySQL 多池）+ B 端 cookie / C 端 RS256 JWT 登录 + 客服接管 + 反向 webhook |
| **MVP-3** | 见下 |

**MVP-3（15 个 task 全部完成）**：
1. 事项中心 HMAC **双 key 热轮换** + mock 门控（`MOCK_EVENT_CENTER`）
2. **self-check**：`end_turn` 后强制一轮自审修订才流给用户
3. **会话治理**：≤20 轮 / ≤100K token 自动总结开新会话
4. **成本治理**：单 BU/user 单日 token 硬阈值（80% 提醒 / 100% 拒服）
5-8. 客服 **C 方案**：ai_draft 草稿审核、senior/engineer 旁观、代查 AI 工具、转派 + KPI 看板
9. 工单状态 **SSE 长连**替换轮询
10-11. **Prompt 版本化**（按 `subject_id` md5 分桶灰度）+ admin 灰度管理面板
12-13. **/metrics**（Prometheus 埋点）+ Grafana 4 类视角面板 / 告警规则
14. 端到端 7 剧本验收（`server/tests/test_e2e_mvp3.py`）
15. docker-compose 升级 + 阿里云 Prometheus 抓取配置 + 上线 checklist（见 README）

**MVP-3 收尾修复（验收复查后发现"看着像、实则空"的 5 处，已全部补齐）**：
1. **用户端收消息**（曾是真 bug）：客服回复 / 审核通过的草稿之前只 publish 到总线、用户收不到。新增用户侧常驻 SSE `GET /api/v1/conversations/{id}/messages-stream`，前端 `useChat` 订阅，接管/草稿消息实时到达。
2. **多轮上下文**：`run_turn` 现会从 DB 回放会话历史给模型（之前每轮只带当前消息，AI 记不住上文）。
3. **指标补全**：`human_pending` gauge 按 DB 实时刷新；新增 `ticket_resolution_seconds` / `staff_takeover_seconds` 真 histogram + 埋点；Grafana 质量面板换真实 `histogram_quantile`。
4. **prompt 版本实差分**：`v1.0.0`=稳定基线（default），`v1.1.0`=实验版（"回答前先复述确认"增强），灰度 20%（此前两版是同一拷贝）。
5. **engineer 解锁脱敏（§13.3）**：`Tool.supports_unmask` + `dispatch(unmask=...)`（剥离 AI 自带值防自助解锁）；engineer 代查可还原 PII/卡号/规则名，senior 仍脱敏。

## 关键约定 & 易踩的坑

- **身份强制注入**：`agent/tool_router.dispatch` 会把会话的 `subject_id` 强写进工具参数，覆盖 AI 传值——AI 无法跨 BU/用户查数据。改工具时别绕过它。同理 `unmask` 只由 staff 端点（engineer）控制，dispatch 会剥离 AI 传的 `unmask`。
- **runtime 会回放历史**：`run_turn` 未压缩时从 DB 加载该会话历史作上下文（`_load_history`）；超阈值时改用压缩摘要 seed（会话治理）。改 messages 拼装逻辑时注意这两条路径。
- **客服↔用户消息靠总线**：人工接管 / ai_draft 模式下，用户的 chat SSE 是 per-message 的，发完即关；客服回复 / 草稿审核结果走**用户侧常驻流** `messages-stream`（订阅 `_subscribers` 总线，只转发 `USER_FACING_EVENTS`）。别以为 chat SSE 能收到客服消息。
- **prompt 走版本注册表**：不要直接读 flat 文件。版本目录 `prompts/v1.x.x/` + `registry.yaml`；用 `loader.read_prompt(key, ...)` / `build_system_blocks(...)`。默认 `v1.0.0`、`v1.1.0` 灰度 20%；改灰度走 `/admin/prompts`（admin 角色，热加载）。
- **事项中心回调验签**：`/api/v1/tickets/{id}/events` 试 `EVENT_CENTER_SECRET_CURRENT` 与 `_PREVIOUS` 两把 key，轮换不停服。
- **SSE 事件总线**：`api/staff_conversations` 的 `_subscribers` 按 conversation_id 分发；客服 stream / 旁观 / 工单状态推送 / 用户侧 messages-stream 都复用它（`register_subscriber` / `publish_conversation_event`）。
- **CWD 注意**：`make` 目标自带 `cd server` / `cd web`；手动跑工具时记得先进对应子目录（venv 在 `server/.venv`）。

## 上线前仍需补的两项（非代码）

- `APP_JWT_PUBLIC_KEY`：填真实 APP 后端 RS256 验签公钥（claims `typ="c"` / `sub=user_id`）。
- `query_*` 工具的表名 / 字段：当前按推测 schema（标 `# TODO`），拿到真实 MySQL schema dump 后按 spec §5.5.1 校对。

## 跨端同步提醒

改动若涉及 backend / web 的契约（SSE 事件、API 路径、鉴权），两端都要同步并各自过门禁；纯单端内部实现不必。
