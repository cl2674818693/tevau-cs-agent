# 贡献指南

## 工程规范基线

所有 commit 必须通过 pre-commit hook；CI 会再跑一遍。绕过 hook（`--no-verify`）一律拒收 PR。

## 项目布局

- `server/`：后端（Python / FastAPI）。命令在 `server/` 下跑（`cd server && ...`）。
- `web/`：前端（Vite + React）。命令在 `web/` 下跑（`cd web && ...`）。
- 顶层：共用 `Makefile`（聚合）、`.gitignore`、`.pre-commit-config.yaml`、`.gitlab-ci.yml`、`docs/`。

## 安装

```bash
(cd server && uv pip install -e ".[dev]")
pre-commit install
pre-commit install --hook-type commit-msg
```

## Commit 规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

- **types**: feat / fix / refactor / test / docs / chore / perf / build / ci / style
- **scopes**: mvp-1 / mvp-2 / mvp-3 / spec / plan / docs / engine / web / staff / db / prompt
- **subject** ≤ 72 字符，描述"做了什么"（祈使句、不用句号）
- 必要时 body 描述"为什么"

例：

```
feat(mvp-1): 添加 search_code 工具（Sourcegraph GraphQL）
fix(engine): tool_router 漏注入 conversation_id（create_ticket 因此报错）
docs(spec): §13.10 加 tawk.to 并存期
```

## 架构约束（违反者拒收 PR）

### 工具与数据安全（spec §2.3 / §4.2 / §5.4）

- ❌ 禁止在 `query_*` handler **外面**写自由 SQL
- ❌ 禁止用 f-string / % 拼接 SQL（必须参数化绑定 `(%s, %s, ...)`）
- ❌ 禁止绕过 `tool_router` 直接调工具 handler（破坏身份注入 + 审计）
- ✅ 所有 `query_*` 工具必须做工具层脱敏（手机/卡号/邮箱/规则名，见 spec §5.4）
- ✅ AI 工具 `requires_subject_id=True` 必须正确设置

### Prompt 与模型

- ❌ prompt 文件**绝不**出现具体人名（嘉豪 / 张三 / CTO 实名等）、内部规则名（R-217）、值班表
- ❌ 不在 .py 文件里硬编码 prompt 文本（所有 prompt 在 `server/src/ai_engine/prompts/` 下）
- ❌ 不在代码里硬编码模型 ID（通过 `settings.default_model` / `settings.heavy_model`）

### 代码结构

- 单文件 ≤ 300 行（超过强 warning，考虑拆分）
- 单函数 ≤ 80 行
- 圈复杂度 ≤ 10（ruff C90 强制）
- 严禁 `from x import *`
- 顶层 `if __name__ == "__main__"` 只在 `scripts/` 下出现

### 前端

- 单组件文件 ≤ 250 行（>250 拆 children）
- 不用 `any`（除非有 `// eslint-disable-next-line` 注释解释）
- 业务 fetch 必须封装在 `web/src/api/` 或 `useXxx` hooks 里，不在组件 inline

### 测试

- 每个 PR 至少包含一个新增/修改的测试
- 覆盖率 ≥ 75%（MVP-1）/ 80%（MVP-2）/ 85%（MVP-3）
- 测试不依赖外部网络（mock 所有外部调用：Anthropic / Sourcegraph / Lark / 事项中心 / GitLab）
- 数据库测试用 `temp_db_url` fixture（内存或临时文件）

### 密码与密钥

- ❌ **绝不**在任何 git 文件出现密码（gitleaks 自动拦）
- ❌ `.env` 必须在 `.gitignore`
- ✅ 测试用明确假值：`sk-ant-test` / `mvp1-shared-secret` / `test-secret`
- ✅ 真实密码只进本机 `.env` 或 vault

### Workflow

- 大改动先在 spec 改、确认设计、再开 plan task
- 不主动重构与当前 task 无关的代码
- 不主动合并 commit（每个 task 一个 commit，方便回滚）

## 跑全套检查

```bash
make lint        # cd server && ruff check + ruff format --check
make typecheck   # cd server && mypy src
make test        # cd server && pytest 含覆盖率
make web-lint    # cd web && pnpm lint + pnpm typecheck
```

CI 跑这四条 + e2e。
