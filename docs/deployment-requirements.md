# cs-engine 部署需求清单（给运维）

cs-engine 是 Tevau 客服 AI 引擎，后端 Python FastAPI（**不是 Java Spring Cloud**，公司无现成模板），前端 Vite + React。本文档列出后端部署到 ACK **开发集群**所需的中间件、资源、域名和网络依赖。

代码仓库：
- 后端：`gitlab.tevaupay.com/tevaupay/infrastructure/tevau-cs-engine-server`（代码在 **test** 分支）
- 前端：`gitlab.tevaupay.com/tevaupay-views/miscellaneous/tevau-cs-engine-web`（走公司前端统一 Jenkins 模板）

---

## 1. 必需中间件

### 1.1 MySQL（自有库）

| 项 | 值 |
| --- | --- |
| 用途 | cs-engine 自有库：存对话/工单/客服账号/审计/token 计量 |
| 实例 | 公司 MySQL RDS（可与业务库 `unlimitpay_test` 同一实例，独立 schema） |
| 库名 | `ai_engine`（字符集 `utf8mb4` / 排序规则 `utf8mb4_unicode_ci`） |
| 账号 | 需要该库**完整读写权限**（用于 `alembic upgrade head` 建表 + 持续读写）；与业务库只读账号 `tevau_test_read` 不同 |
| 注入环境变量 | `DB_URL=mysql+aiomysql://<user>:<pwd>@<host>:3306/ai_engine` |

> 自有库 MySQL 是硬依赖：缺失则后端启动时连不上库直接 fail。
>
> 不复用 `tevau_test_read`：那是业务库只读账号，cs-engine 自有库要持续写入对话/工单数据，必须独立读写账号 + 独立库，避免污染业务库。

### 1.2 Redis

| 项 | 值 |
| --- | --- |
| 用途 | 限流计数（多副本全局精确滑动窗口）+ 工具结果缓存 |
| 来源 | 复用公司开发环境现有共享 Redis 即可，无需新建 |
| 注入环境变量 | `REDIS_URL=redis://<host>:6379/0` |

> 无 Redis 限流会回退到进程内（仅单副本可用，多副本不一致）；开发环境单副本可以暂缓但建议挂上。

---

## 2. 复用现有资源（无需新建）

### 2.1 MySQL RDS 业务库只读账号

| 项 | 值 |
| --- | --- |
| 用途 | cs-engine 用 AI 工具回答用户问题时查业务数据（订单/KYC/风控等） |
| 实例 | 阿里云 RDS 现有 `rm-gs5bk11j43yl6jxt4.mysql.singapore.rds.aliyuncs.com:3306` |
| 库 | `unlimitpay_test`（C 端业务）+ `tevau_nexus_test`（B 端业务） |
| 账号 | 现有 `tevau_test_read`（只读，复用） |
| 注入环境变量 | `UNLIMITPAY_DB_URL` / `NEXUS_DB_URL`（mysql+aiomysql:// 连接串） |

---

## 3. 可选中间件（开发环境可延后）

### 3.1 OSS（S3 兼容对象存储）

| 项 | 值 |
| --- | --- |
| 用途 | 存对话中用户上传的图片附件 |
| 缺失影响 | 用户对话不能发图片，**其他功能不受影响** |
| 建议 bucket 名 | `cs-engine-attachments-dev` |
| 注入环境变量 | `OBJECT_STORE_ENDPOINT` / `OBJECT_STORE_BUCKET` / `OBJECT_STORE_ACCESS_KEY` / `OBJECT_STORE_SECRET_KEY` |

---

## 4. 持久化卷（非中间件）

后端容器 `/repos` 路径需要挂载**持久卷 ≥ 5GB**，结构如下：

```
/repos/
  code/
    app_frontend/      <- Flutter APP 仓库副本（GitLab 拉）
    app_backend/       <- TevauPay-Service 副本（C 端 APP 后端）
    openapi_backend/   <- TevauNexus-Service 副本（B 端 OpenAPI 后端）
```

部署侧需要做的：

- **首次部署**：把上述 3 个仓库 clone 进 PV
- **保持新鲜**：CronJob 每 30 分钟在 PV 里跑一次 `git pull`（不更新会让 cs-engine 回答用户问题时引用过时代码）

---

## 5. 域名 / Ingress

| 项 | 值 |
| --- | --- |
| 域名 | 类似 `cs-engine-dev.tevau.internal`，按公司命名规则分配 |
| 协议 | HTTP 即可（开发环境） |
| 反代目标 | 后端 Service `cs-engine-api:8000` |

**重要**：cs-engine 用 Server-Sent Events (SSE) 长连接推消息给前端，Ingress 需要做这些配置（nginx-ingress 注解示例）：

```yaml
nginx.ingress.kubernetes.io/proxy-buffering: "off"
nginx.ingress.kubernetes.io/proxy-read-timeout: "86400"
nginx.ingress.kubernetes.io/proxy-send-timeout: "86400"
```

> 不配的话 SSE 会被 Ingress 缓冲 + 60s 默认超时切断，对话框消息推不出来。

---

## 6. 外部网络依赖（请确认 Pod 出口能访问）

| 服务 | 地址 | 用途 |
| --- | --- | --- |
| 开发环境事项中心 | `http://192.168.2.6:822/api/tasks` | cs-engine 推工单到事项中心 |
| C 端 APP 网关 | `https://test2.tevaupay.com/gateway` | cs-engine 调它换 C 端用户身份（Sa-Token → userCode） |
| Anthropic API | `https://api.anthropic.com`（或公司 LLM 网关） | 调 Claude 大模型 |

> 192.168.2.6 是公司内网地址，请确认 ACK 开发集群 Pod 出口路由能到这台机。

---

## 7. 镜像构建

- 构建上下文：`server/`
- Dockerfile：`server/Dockerfile`（多阶段，基于 `python:3.12-slim`）
- 本地 build 验证产出镜像 ~602MB
- 暴露端口：`8000`
- 健康检查路径：`GET /healthz`（readinessProbe + livenessProbe）
- Metrics：`GET /metrics`（Prometheus 格式，可选鉴权 `METRICS_AUTH_TOKEN`）

---

## 8. 资源建议（参考值，按实际调整）

| 资源 | requests | limits |
| --- | --- | --- |
| CPU | 200m | 2 |
| 内存 | 512Mi | 2Gi |

- 副本数：开发环境 **1 副本**（自有库 RWO PVC 默认不支持多副本同写）
- `UVICORN_WORKERS=2`（按 Pod CPU 调，一般 = nproc 或 2×nproc+1）
- 部署策略：建议 `Recreate`（单副本 + RWO PVC，RollingUpdate 会卡）

---

## 9. 完整环境变量清单

对照填进运维侧部署模板即可：

- **非敏感配置**：仓库 `k8s/dev/configmap.yaml`（含所有 env 含义注释）
- **敏感凭据**：仓库 `k8s/dev/secret.example.yaml`（模板，填实值后变 Secret）

需要从我这边拿到的"应用专属"机密：

| 项 | 来源 |
| --- | --- |
| `ANTHROPIC_API_KEY` | 我提供 |
| `STAFF_JWT_SECRET` / `BU_SESSION_SECRET` | 我本地 `openssl rand -hex 32` 生成 |
| `EVENT_CENTER_TOKEN` / `EVENT_CENTER_CALLBACK_TOKEN` | 找事项中心同事要 |

---

## 10. 一次性部署后动作

后端 Pod 起来后需要做两件初始化：

1. **跑数据库迁移**：`alembic upgrade head`（建表，仓库 `k8s/dev/migration-job.yaml` 是一次性 Job）
2. **创建初始客服账号**（管理员 + 客服测试账号）：
   ```bash
   kubectl exec deploy/cs-engine-api -- python -c "
   import asyncio
   from ai_engine.persistence.db import init_db
   from ai_engine.persistence.staff import create_staff
   async def main():
       await init_db()
       await create_staff('ADMIN','管理员','admin','请改这个密码')
       await create_staff('CS01','客服一','agent','请改这个密码')
   asyncio.run(main())
   "
   ```

---

## 11. 部署后冒烟测试

域名通了之后访问：

- `http://<域名>/staff/login` 用 ADMIN/初始密码登录客服工作台
- `http://<域名>/bu/login` B 端登录跑一轮 AI 对话 → 触发"转人工"或"创建工单" → 确认事项中心后台（`http://192.168.2.6:822`）能看到对应 task

---

## 12. 前端

cs-engine 前端独立仓库 `tevau-cs-engine-web`，走公司前端 Jenkins 统一模板即可：

- 构建：`pnpm install && pnpm build`（或按环境 `pnpm build:dev` / `build:test` / `build:uat` / `build:pre` / `build:prd`）
- 产物：`dist/`
- 已对齐 `tevau-finance-admin` 风格的 `.env.development/.test/.uat/.pre/.production` 配置

cs-engine 前后端走**同源部署**（前端 nginx serve dist/ + 同一域名反代 `/api`、`/staff/api`、`/admin/api` 到后端 Service）。如果运维偏好前后端拆两个域名也行，前端代码侧改一下 fetch baseURL 即可。

---

## 13. 参考资料

仓库内文档：

- `k8s/dev/README.md` —— 详细操作手册（含 12 节，从拿钥匙到部署到回滚到排错，按需参考）
- `k8s/dev/*.yaml` —— K8S manifest 草稿（不是必须用，仅作"项目侧需求"参考）
- `docs/superpowers/CONTEXT.md` —— 项目背景（产品定位、技术选型）

有任何问题随时联系。
