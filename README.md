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

`make test`
