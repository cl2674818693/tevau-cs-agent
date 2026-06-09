# cs-engine 部署到 ACK 开发集群

把 cs-engine（后端 API + 前端）部署到公司阿里云 ACK **开发集群**的操作手册。

> 这里只覆盖开发环境（namespace: `tevau-cs-engine-dev`）。
> 测试/生产上线时复制此目录改环境特定值（域名 / DB 地址 / 资源大小 / 副本数）。

---

## 0. 前置：从公司要的"钥匙"

部署前你要拿到这些东西，否则推进不下去：

| 项 | 找谁要 | 用途 |
| --- | --- | --- |
| ACK 开发集群 kubeconfig | 运维 | `kubectl` 连集群 |
| Docker Registry push 凭据（地址/账号/密码） | 运维 | 推镜像 |
| 开发环境 MySQL `ai_engine` 库 + 读写账号 | DBA | 自有库（会话/工单/审计/客服） |
| 开发环境 Redis 内网地址 | 运维 | 限流计数（spec §6.4） |
| Ingress 域名（如 `cs-engine-dev.tevau.internal`） | 运维 | 用域名访问 cs-engine |
| 业务库 `tevau_test_read` 密码 | 后端 | 业务库只读查询 |
| 事项中心出站 token (`EVENT_CENTER_TOKEN`) | 事项中心同事 | cs-engine→事项中心 Authorization |
| 事项中心回调 token (`EVENT_CENTER_CALLBACK_TOKEN`) | 事项中心同事 | 事项中心→cs-engine 验签 |
| `ANTHROPIC_API_KEY` | 已有 | 调 Claude |

可选（开发环境不强依赖）：
- OSS bucket + AccessKey（图片附件用；不配则用集群内 MinIO 或先关闭附件功能）
- Lark webhook URL（差评/工单兜底告警；空则不通知）

---

## 1. 一次性准备

### 1.1 安装 kubectl，配 kubeconfig

```bash
# macOS
brew install kubectl

# 把运维给的 kubeconfig 放到 ~/.kube/config，或用 KUBECONFIG 环境变量指
export KUBECONFIG=/path/to/ack-dev-kubeconfig.yaml
kubectl get nodes   # 能列出节点说明连上了
```

### 1.2 建 namespace

```bash
kubectl apply -f k8s/dev/namespace.yaml
```

### 1.3 登录 Docker Registry

```bash
docker login <NEXUS_DOCKER_HOST>   # 用运维给的账号密码
```

如果 ACK 拉镜像需要鉴权，把这套凭据塞进集群：

```bash
kubectl -n tevau-cs-engine-dev create secret docker-registry nexus-docker-creds \
  --docker-server=<NEXUS_DOCKER_HOST> \
  --docker-username=<USER> \
  --docker-password=<PWD>
```

然后在 `api-deployment.yaml` / `web-deployment.yaml` / `migration-job.yaml` 里把 `imagePullSecrets` 那几行的注释打开。

---

## 2. 构建 + 推镜像

仓库根执行：

```bash
# 替换 <NEXUS_DOCKER_HOST> 和 tag
export REGISTRY=<NEXUS_DOCKER_HOST>
export TAG=dev-$(git rev-parse --short HEAD)

# 后端
docker build -t $REGISTRY/tevau-cs-engine-api:$TAG ./server
docker push $REGISTRY/tevau-cs-engine-api:$TAG

# 前端
docker build -t $REGISTRY/tevau-cs-engine-web:$TAG ./web
docker push $REGISTRY/tevau-cs-engine-web:$TAG
```

把 manifest 里 `<NEXUS_DOCKER>/tevau-cs-engine-{api,web}:dev-latest` 三处统一替换为
`$REGISTRY/tevau-cs-engine-{api,web}:$TAG`：

```bash
# 一次性 sed 替换三个文件（macOS 注意空 -i 参数）
sed -i.bak "s|<NEXUS_DOCKER>|$REGISTRY|g; s|:dev-latest|:$TAG|g" \
  k8s/dev/api-deployment.yaml k8s/dev/web-deployment.yaml k8s/dev/migration-job.yaml
rm k8s/dev/*.bak
```

> 第一次为了快验证，可以把 tag 写成 `dev-latest` 反复推；
> 稳定后改成带 git sha 的 immutable tag，避免回滚踩坑。

---

## 3. 填 Secret

```bash
cp k8s/dev/secret.example.yaml k8s/dev/secret.yaml
# 编辑 secret.yaml 填实际值（已在 .gitignore，不会被提交）
vim k8s/dev/secret.yaml

# 生成两个 32 字节随机密钥
echo "STAFF_JWT_SECRET=$(openssl rand -hex 32)"
echo "BU_SESSION_SECRET=$(openssl rand -hex 32)"
```

apply：

```bash
kubectl apply -f k8s/dev/secret.yaml
kubectl apply -f k8s/dev/configmap.yaml
```

> 改完 ConfigMap/Secret 要 `kubectl rollout restart deploy/cs-engine-api` Pod 才会拿到新值。

---

## 4. 准备 PVC 内容（代码副本 + openapi.json）

cs-engine 的 `search_code` / `read_file` / `lookup_api_doc` 工具需要：
- 3 个代码仓库副本：`/repos/code/app_frontend`、`/repos/code/app_backend`、`/repos/code/openapi_backend`
- OpenAPI 文档：`/repos/api-docs/*.openapi.json`

先建 PVC：

```bash
kubectl apply -f k8s/dev/pvc-repos.yaml
```

然后用一个临时 Pod 挂上 PVC，把内容塞进去（Pod 跑完删除）：

```bash
# 临时 Pod，shell 进去 git clone
kubectl -n tevau-cs-engine-dev run repos-init --rm -it --restart=Never \
  --image=alpine/git:latest \
  --overrides='{"spec":{"containers":[{"name":"repos-init","image":"alpine/git:latest","command":["sh"],"stdin":true,"tty":true,"volumeMounts":[{"name":"repos","mountPath":"/repos"}]}],"volumes":[{"name":"repos","persistentVolumeClaim":{"claimName":"cs-engine-repos"}}]}}'

# 进容器后执行：
mkdir -p /repos/code /repos/api-docs
cd /repos/code
git clone <Flutter APP 仓库地址>          app_frontend
git clone <TevauPay-Service 仓库地址>     app_backend
git clone <TevauNexus-Service 仓库地址>   openapi_backend
# 然后从你本地 scp/上传 openapi.json：暂时可以先空，工具会回退
exit
```

> 嫌临时 Pod 麻烦也可以走 `kubectl cp` 把本地 `repos/` 整个推上去。

---

## 5. 跑数据库迁移（建表）

```bash
kubectl apply -f k8s/dev/migration-job.yaml
kubectl -n tevau-cs-engine-dev logs job/cs-engine-migrate -f
# 看到 "Running upgrade ... -> head" 完成即可
```

---

## 6. 部署 API 和 Web

```bash
kubectl apply -f k8s/dev/api-service.yaml
kubectl apply -f k8s/dev/api-deployment.yaml
kubectl apply -f k8s/dev/web-service.yaml
kubectl apply -f k8s/dev/web-deployment.yaml

# 看 Pod 起来没
kubectl -n tevau-cs-engine-dev get pods -w
```

API Pod 第一次启动可能 30-60s（要装/初始化 anthropic SDK）。看日志：

```bash
kubectl -n tevau-cs-engine-dev logs deploy/cs-engine-api -f
```

---

## 7. 暴露域名（Ingress）

先确认运维给你分配的域名和 ingressClassName：

```bash
kubectl get ingressclass   # 看可用 class（nginx / alb / mse）
```

改 `ingress.yaml` 里的 `host:` 和 `ingressClassName:`，然后：

```bash
kubectl apply -f k8s/dev/ingress.yaml
```

把域名指向 Ingress 暴露的 LB IP（通常运维 DNS 那边做）。

---

## 8. 创建客服初始账号

cs-engine 客服账号独立系统（不复用 SSO）：

```bash
kubectl -n tevau-cs-engine-dev exec deploy/cs-engine-api -- python -c "
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

## 9. 冒烟测试

打开浏览器 `http://cs-engine-dev.tevau.internal/`：

1. 访问 `/staff/login` 用 `ADMIN / 请改这个密码` 登录客服工作台
2. 访问 `/bu/login` 走 B 端登录跑一轮问答
3. 让 AI 触发"转人工"或"创建工单"，确认事项中心后台（http://192.168.2.6:822）能看到对应 task
4. `kubectl -n tevau-cs-engine-dev logs deploy/cs-engine-api | grep ERROR` 看有没有报错

---

## 10. 常见问题

### Pod CrashLoopBackOff / 起不来
看日志：`kubectl -n tevau-cs-engine-dev logs deploy/cs-engine-api`
常见原因：
- `DB_URL` 连不上 MySQL ai_engine 库（看是不是内网地址 / 账号密码错）
- `STAFF_JWT_SECRET` / `BU_SESSION_SECRET` 没填（config.py 里设 `required` 起步就 fail）
- 业务库密码错（这个不会让 api 启动失败，但查询时报错）

### Pod 起来了但 `/healthz` 502
- 检查 api Pod 端口（`kubectl describe pod`）
- `UVICORN_WORKERS` 内存不够导致 worker fork 失败 → 调小或加 memory limit

### web 访问 404 但 API 直连正常
- nginx.conf 反代前缀漏配，或 API_UPSTREAM 写错了
- `kubectl exec deploy/cs-engine-web -- cat /etc/nginx/conf.d/default.conf` 看渲染结果

### 事项中心连不通
- ACK Pod 出口能不能访问 192.168.2.6？让运维确认 VPC/专线
- `kubectl exec deploy/cs-engine-api -- curl -v http://192.168.2.6:822/` 测一下

### 改了 ConfigMap 不生效
- ConfigMap 通过 envFrom 注入是启动时一次性读的，要 `kubectl rollout restart deploy/cs-engine-api` 才会拿新值

---

## 11. 升级/回滚

```bash
# 推新镜像后改 deployment 的 image tag
kubectl -n tevau-cs-engine-dev set image deploy/cs-engine-api api=$REGISTRY/tevau-cs-engine-api:$NEW_TAG
kubectl -n tevau-cs-engine-dev rollout status deploy/cs-engine-api

# 回滚
kubectl -n tevau-cs-engine-dev rollout undo deploy/cs-engine-api
```

数据库迁移：`kubectl delete job cs-engine-migrate && kubectl apply -f k8s/dev/migration-job.yaml`。

---

## 12. 卸载（清理）

```bash
kubectl delete namespace tevau-cs-engine-dev   # 一键清掉所有资源（含 PVC，数据会丢）
```
