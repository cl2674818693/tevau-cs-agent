# Task 14: docker-compose + Sourcegraph + 部署文档收尾

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `docker-compose.yml`（仓库根）
- Create: `server/Dockerfile`（后端构建上下文 = `server/`）
- Modify: `README.md`（追加部署 + Sourcegraph 首次配置小节）

> 双子项目布局调整（实际实现）：Dockerfile 放 `server/`，compose `api.build: ./server`；环境变量加 `ANTHROPIC_BASE_URL`（自建网关）；`web` 服务 `pnpm install` 带 `CI=true`（pnpm 10 非交互）；Dockerfile 先 COPY src 再 `uv pip install -e .`（editable，让 prompts .md 直接可读）。`.env` 路径是 `server/.env`。

- [ ] **Step 1: 写 `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -e ".[dev]"
COPY src ./src
CMD ["uvicorn", "ai_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> 不再安装 ripgrep —— Task 4 改用 Sourcegraph GraphQL，代码索引在独立容器跑。

- [ ] **Step 2: 写 `docker-compose.yml`**

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DB_URL=sqlite+aiosqlite:////data/ai_engine.db
      - SOURCEGRAPH_URL=http://sourcegraph:7080
      - SOURCEGRAPH_TOKEN=${SOURCEGRAPH_TOKEN}
      - OPENAPI_DOC_PATH=/repos/api-docs/openapi.json
      - PROMPTS_DIR=/app/src/ai_engine/prompts
      - EVENT_CENTER_URL=${EVENT_CENTER_URL:-http://api:8000/_mock/event-center}
      - EVENT_CENTER_SECRET=${EVENT_CENTER_SECRET:-mvp1-shared-secret}
      - LARK_WEBHOOK_URL=${LARK_WEBHOOK_URL:-}
    volumes:
      - ./data:/data
      - ./repos:/repos:ro
    depends_on:
      - sourcegraph

  sourcegraph:
    image: sourcegraph/server:5.3.0
    ports: ["7080:7080"]
    volumes:
      - sg-config:/etc/sourcegraph
      - sg-data:/var/opt/sourcegraph
    restart: unless-stopped

  web:
    image: node:20-alpine
    working_dir: /web
    volumes: ["./web:/web"]
    command: sh -c "corepack enable && pnpm install && pnpm dev --host 0.0.0.0"
    ports: ["5173:5173"]
    depends_on: [api]

volumes:
  sg-config:
  sg-data:
```

- [ ] **Step 3: 修 `README.md` 加部署小节**

在文件末尾追加：

```markdown
## 容器化启动

### 第一次启动顺序

```bash
cp .env.example .env  # 填 ANTHROPIC_API_KEY（暂留 SOURCEGRAPH_TOKEN 空）
mkdir -p data repos/api-docs

# 1. 先只起 sourcegraph 做初始化
docker compose up -d sourcegraph

# 2. 浏览器打开 http://localhost:7080
#    - 创建 admin 账号
#    - Settings → Access tokens → 生成一个新 token，复制到 .env 的 SOURCEGRAPH_TOKEN
#    - Site admin → External services → Add GitLab connector
#      - URL: https://gitlab.tevaupay.com
#      - Token: 一个 GitLab personal access token（scope: api、read_repository）
#      - 仓库白名单（projectQuery 或 projects）加上：
#          tevaupay-views/app/TevauPay-Flutter
#          tevaupay/business-services/TevauPay-Service
#          tevaupay/business-services/TevauNexus-Service
#      - 等 indexing 完成（首次 5-30 分钟，看仓库大小）

# 3. 从 Apifox 项目导出 OpenAPI 3.0 JSON → 放到 repos/api-docs/openapi.json

# 4. 起 api + web
docker compose up --build api web
```

后端 :8000，前端 :5173，Sourcegraph :7080。

### 日常启动

```bash
docker compose up
```

(Sourcegraph 数据持久化在 docker volume，不会丢)
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml Dockerfile README.md
git commit -m "chore: docker-compose 加 sourcegraph 服务 + 首次配置文档"
```

> **MVP-1 部署阻塞依赖（spec §12.2 待协作产出项，上线前必须有）**：
> - `SOURCEGRAPH_TOKEN`：自部署后从 Sourcegraph 后台生成
> - GitLab personal access token（配在 Sourcegraph 后台，不进 AI 引擎 .env）
> - `LARK_WEBHOOK_URL`：现"Open Api 问题工单通知群"机器人 webhook 地址
> - `repos/api-docs/openapi.json`：从 Apifox 导出

---
