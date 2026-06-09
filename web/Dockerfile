# 阶段 1：用 node 跑 vite build，产物在 /web/dist
# Node 22：pnpm 11 + package.json packageManager 锁定要求 Node >= 22.13
FROM node:22-alpine AS builder
WORKDIR /web

# 先复制依赖清单，让 pnpm install 层在依赖未变时命中缓存
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# pnpm 10+ 默认拒绝依赖跑 build 脚本（esbuild 装不上）；
# dangerouslyAllowAllBuilds 非交互批准全部 build。
RUN corepack enable \
    && pnpm install --frozen-lockfile --config.dangerouslyAllowAllBuilds=true

# 复制源码并构建
COPY . .
RUN pnpm build

# 阶段 2：nginx 提供静态文件 + 反代 api
FROM nginx:1.27-alpine AS runtime
# 用 envsubst 模板：K8S 注入 API_UPSTREAM=http://cs-engine-api:8000
# nginx:alpine 启动脚本会自动把 /etc/nginx/templates/*.template 渲染到 /etc/nginx/conf.d/
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /web/dist /usr/share/nginx/html

EXPOSE 80
