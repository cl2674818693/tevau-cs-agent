# Tevau 客服工单 AI 引擎 (MVP-1)

把开发者用 Claude 看代码、查数据库的体验，包装成一个专门答 Tevau Open API / APP 问题的对话框，工具受限、身份隔离、可审计。详见 [`docs/superpowers/CONTEXT.md`](docs/superpowers/CONTEXT.md)。

## 项目布局

- `server/`：后端（Python / FastAPI + Anthropic SDK）
- `web/`：前端（Vite + React，Task 12 起创建）
- `docs/`：设计与计划文档

## 启动

1. 复制 `server/.env.example` 为 `server/.env`，填 `ANTHROPIC_API_KEY`（公司网关填 `ANTHROPIC_BASE_URL`）
2. `make install`
3. `make run`（后端，默认 :8000）
4. `make web-install && make web-dev`（前端，默认 :5173）

## 测试

`make test`（后端 pytest）/ `make web-test`（前端 vitest）

## 容器化启动

后端镜像构建上下文是 `server/`（见 `server/Dockerfile`），`docker-compose.yml` 在仓库根。

### 第一次启动顺序

```bash
cp server/.env.example server/.env   # 填 ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL（暂留 SOURCEGRAPH_TOKEN 空）
mkdir -p data repos/api-docs

# 1. 先只起 sourcegraph 做初始化
docker compose up -d sourcegraph

# 2. 浏览器打开 http://localhost:7080
#    - 创建 admin 账号
#    - Settings → Access tokens → 生成 token，复制到 .env 的 SOURCEGRAPH_TOKEN
#    - Site admin → External services → Add GitLab connector
#      - URL: https://gitlab.tevaupay.com，Token: GitLab PAT（scope: api、read_repository）
#      - 仓库白名单：
#          tevaupay-views/app/TevauPay-Flutter
#          tevaupay/business-services/TevauPay-Service
#          tevaupay/business-services/TevauNexus-Service
#      - 等 indexing 完成（首次 5-30 分钟）

# 3. 从 Apifox 导出 OpenAPI 3.0 JSON → repos/api-docs/openapi.json

# 4. 起 api + web
docker compose up --build api web
```

后端 :8000，前端 :5173，Sourcegraph :7080。日常启动 `docker compose up`（Sourcegraph 数据持久化在 docker volume）。

### 上线前必须有的外部依赖（spec §12.2）

- `SOURCEGRAPH_TOKEN`：Sourcegraph 后台生成
- GitLab PAT：配在 Sourcegraph 后台（不进 AI 引擎 .env）
- `LARK_WEBHOOK_URL`：现"Open Api 问题工单通知群"机器人 webhook
- `repos/api-docs/openapi.json`：从 Apifox 导出

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

后端 `GET /metrics` 暴露 Prometheus 指标（`ai_engine_*`：active_conversations、tool_calls/duration、llm_calls/tokens、tickets、staff_takeovers、user_resolved）。

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

> 成本估算 panel 按 sonnet 价（input $3/M、output $15/M）估算，按实际合同价调整系数；工单 SLA / 接管时长 histogram 待后续埋点补全（当前用接管次数与解决率近似）。
