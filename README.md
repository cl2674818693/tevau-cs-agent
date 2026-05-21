# Tevau 客服工单 AI 引擎 (MVP-1)

把开发者用 Claude 看代码、查数据库的体验，包装成一个专门答 Tevau Open API / APP 问题的对话框，工具受限、身份隔离、可审计。详见 [`docs/superpowers/CONTEXT.md`](docs/superpowers/CONTEXT.md)。

## 项目布局

- `server/`：后端（Python / FastAPI + Anthropic SDK）
- `web/`：前端（Vite + React，Task 12 起创建）
- `docs/`：设计与计划文档

## 启动

1. 复制 `server/.env.example` 为 `server/.env`，填 `ANTHROPIC_API_KEY`（公司网关填 `ANTHROPIC_BASE_URL`）
2. `make install`
3. （可选，启用代码搜索）软链/clone 4 个仓库到 `repos/code/<别名>`，并在 `server/.env` 配 `CODE_REPO_PATHS`（见下「代码仓库同步」）
4. `make run`（后端，默认 :8000）
5. `make web-install && make web-dev`（前端，默认 :5173）

## 测试

`make test`（后端 pytest）/ `make web-test`（前端 vitest）

## 容器化启动

后端镜像构建上下文是 `server/`（见 `server/Dockerfile`），`docker-compose.yml` 在仓库根。

### 第一次启动顺序

```bash
cp server/.env.example server/.env   # 填 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL
mkdir -p data repos/api-docs repos/code

# 1. 准备代码仓库副本（search_code/read_file 直接搜读本地代码，按固定别名 clone）
git clone <Flutter APP 仓库>       repos/code/app_frontend
git clone <TevauPay-Service>       repos/code/app_backend
git clone <TevauNexus-Service>     repos/code/openapi_backend

# 2. 从 Apifox 导出 OpenAPI 3.0 JSON → repos/api-docs/openapi.json

# 3. 起 api + web
docker compose up --build api web
```

后端 :8000，前端 :5173。compose 把 `./repos` 挂载为容器内 `/repos`（只读）；
`CODE_REPO_PATHS` 已在 `docker-compose.yml` 配好指向 `/repos/code/<别名>`。

### 代码仓库同步（search_code / read_file 依赖）

代码搜索/读取直接走 `repos/code/` 下的本地副本（**不用 Sourcegraph，无 license 限制**）：

- 代码**不打进镜像**，通过挂载卷提供 → 镜像保持小、代码可独立更新。
- 3 个别名固定：`app_frontend`(Flutter APP) / `app_backend`(C端APP后端) / `openapi_backend`(B端OpenAPI)。管理后台（admin_backend）含内部风控/审核逻辑，不暴露给面向用户的 AI，已从白名单移除。
- **保持代码新鲜**：加定时拉取，例如 cron 每 30 分钟：
  ```bash
  */30 * * * * cd /srv/tevau-cs-engine/repos/code && for d in */; do (cd "$d" && git pull -q); done
  ```
- 本地开发可用软链代替 clone：`ln -sfn <本地仓库绝对路径> repos/code/<别名>`（`search_code` 会 realpath 解析软链）。

### 上线前必须有的外部依赖（spec §12.2）

- `repos/code/<别名>`：4 个代码仓库副本 + 定时 `git pull`（见上）
- `repos/api-docs/openapi.json`：从 Apifox 导出（`lookup_api_doc` 用）
- `LARK_WEBHOOK_URL`：现"Open Api 问题工单通知群"机器人 webhook
- 业务库：`UNLIMITPAY_DB_URL` / `NEXUS_DB_URL`（阿里云 RDS 只读账号）
- C 端身份对接：见 [`docs/backend-understanding/identity-and-auth.md`](docs/backend-understanding/identity-and-auth.md)（Sa-Token → getCurrentUserInfo → user_id）

## MVP-2 增量（业务库 / 客服 / B 端登录）

### 本地 MySQL（compose 自带）

`docker compose up mysql` 会起一个 MySQL 8 并用 `server/tests/fixtures/unlimitpay_seed.sql` 初始化（bu / user / card / api_call_log 样本）。`.env` 设：

```bash
MYSQL_PASSWORD=readpass                 # compose mysql 的 tevau_test_read 密码
STAFF_JWT_SECRET=$(openssl rand -hex 32)  # 客服 JWT 签名密钥（≥32 字节）
# UNLIMITPAY_DB_URL 默认指向 compose 的 mysql；生产改为阿里云 RDS 只读账号（见 docs/resources.md）
```

> 生产 `UNLIMITPAY_DB_URL` / `NEXUS_DB_URL` 用阿里云 RDS 的**只读账号**（`tevau_test_read`），不是 compose 里的 dev 账号。query_* 工具的表名/字段当前按推测 schema（标 `# TODO`），拿到真实 schema dump 后校对（spec §12.2 第 9 条）。

### 客服账号初始化

客服账号独立系统（spec §12.5 ✅3，不复用 SSO）。手动建账号：

```bash
docker compose exec api python -c "import asyncio; from ai_engine.persistence.db import init_db; from ai_engine.persistence.staff import create_staff; asyncio.run((lambda: (init_db(), create_staff('S100','客服张三','agent','改我')))())"
```

客服工作台访问 `http://localhost:5173/staff/login`。

### C 端 APP JWT（已实现，仅需配公钥）

C 端身份链路已落地（`auth/c_jwt.py` 验签 RS256；`resolve_identity` Bearer C-JWT 优先、cookie/X-BU-ID 回退；chat / conversations / 反向 webhook 两端通用）。**生产上线只需把 APP 后端的 RS256 公钥填进 `APP_JWT_PUBLIC_KEY`**（claims 约定 `typ="c"` / `sub=user_id`，spec §4.1）。前端 `useAppBridge` 已就绪接收 APP 注入的 JWT。

## MVP-3 可观测性（Prometheus + Grafana）

后端 `GET /metrics` 暴露 Prometheus 指标（`ai_engine_*`：active_conversations、human_pending、tool_calls/duration、llm_calls/tokens、tickets + ticket_resolution_seconds、staff_takeovers + staff_takeover_seconds、user_resolved）。

### 接入步骤

1. Prometheus 抓取后端 `/metrics`（默认 :8000），并在 `rule_files` 引入 `grafana/alerts.rules.yml`：
   ```yaml
   scrape_configs:
     - job_name: tevau-ai-engine
       static_configs: [{ targets: ["api:8000"] }]
   rule_files:
     - /etc/prometheus/alerts.rules.yml   # 挂载 grafana/alerts.rules.yml
   ```
2. Grafana → Dashboards → Import → 上传 `grafana/tevau-ai-engine.dashboard.json`，选择 Prometheus 数据源。
3. 面板含 4 类视角：实时运营 / 趋势（含成本估算）/ 质量 / 告警（规则在 `alerts.rules.yml`）。

> 成本估算 panel 按 sonnet 价（input $3/M、output $15/M）估算，按实际合同价调整系数。工单解决耗时（`ticket_resolution_seconds`）、客服接管时长（`staff_takeover_seconds`）已为真实 histogram，面板用 `histogram_quantile` 出 p50/p90；`human_pending` gauge 按 DB 实时刷新。

阿里云 Prometheus 抓取配置示例见 `infra/prometheus-scrape-config.example.yaml`。

## MVP-3 上线 checklist

环境变量（compose 的 `api` 服务已就位，生产填实值）：

```bash
ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL   # 公司网关
APP_JWT_PUBLIC_KEY                        # C 端 APP RS256 验签公钥（typ=c / sub=user_id）
STAFF_JWT_SECRET=$(openssl rand -hex 32)
EVENT_CENTER_URL                          # 真事项中心接收地址
EVENT_CENTER_SECRET_CURRENT               # 当前 HMAC key；轮换时把旧值挪到 PREVIOUS
EVENT_CENTER_SECRET_PREVIOUS              # 轮换窗口内的旧 key（平时留空）
MOCK_EVENT_CENTER=false                   # 生产必须 false
DAILY_TOKEN_LIMIT=500000                  # 单 BU/单 user 单日 token 上限
UNLIMITPAY_DB_URL / NEXUS_DB_URL          # 阿里云 RDS 只读账号
LARK_WEBHOOK_URL                          # 工单兜底通知群
```

上线步骤：

1. **事项中心连通性**：建一条测试工单确认真事项中心收到并回 `internal_ticket_id`；用 `EVENT_CENTER_SECRET_CURRENT` 签一条 `assigned` 回调到 `POST /api/v1/tickets/{id}/events` 验签通过。
2. **HMAC 双 key 初始化**：首发只填 `CURRENT`；轮换时新 key 进 `CURRENT`、旧 key 进 `PREVIOUS`，确认两把 key 都验签通过后再清空 `PREVIOUS`（验证：`server/tests/test_event_center_dual_key.py`）。
3. **Grafana**：导入 `grafana/tevau-ai-engine.dashboard.json`，加载 `grafana/alerts.rules.yml`，确认 `/metrics` 被抓取。
4. **客服账号批量初始化**（前 2 名 APP 客服 + 嘉豪 + 另一对接人 + 1 个 admin）：

   ```bash
   docker compose exec api python -c "
   import asyncio
   from ai_engine.persistence.db import init_db
   from ai_engine.persistence.staff import create_staff
   async def main():
       await init_db()
       await create_staff('CS01','客服一','agent','改我')
       await create_staff('CS02','客服二','agent','改我')
       await create_staff('JIAHAO','嘉豪','engineer','改我')
       await create_staff('PARTNER','对接人','senior','改我')
       await create_staff('ADMIN','管理员','admin','改我')
   asyncio.run(main())
   "
   ```

   admin 登录后可在 `/admin/prompts` 调 prompt 灰度比例（spec §8）。
5. **冒烟**：B 端 `http://<host>:5173/bu/login` 走一轮问答 + 转人工；客服 `/staff/login` 接管/转派/标记解决；确认工单状态经 SSE 推回对话框。
