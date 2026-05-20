# Task 0: 工程规范基线（必须先于业务代码）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**目的**：建立 lint / type-check / pre-commit / CI / commit / 架构约束基线。后续所有 task 的代码必须通过这些约束才能提交。**不做 Task 0 直接干 Task 1+ 一定会让后期维护痛苦**。

**Files:**
- Create: `server/pyproject.toml`（强化版，覆盖整个 MVP 期间）
- Create: `.gitignore`
- Create: `.pre-commit-config.yaml`
- Create: `.gitleaks.toml`
- Create: `scripts/check_commit_msg.sh`
- Create: `CONTRIBUTING.md`
- Create: `.gitlab-ci.yml`

- [ ] **Step 1: 创建强化版 `server/pyproject.toml`**

```toml
[project]
name = "ai-engine"
version = "0.1.0"
description = "Tevau 客服工单 AI 引擎"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "anthropic>=0.40",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "httpx>=0.27",
  "sse-starlette>=2.1",
  "aiosqlite>=0.20",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.24",
  "pytest-cov>=5",
  "ruff>=0.6.8",
  "mypy>=1.11",
  "respx>=0.21",
  "pre-commit>=3.7",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--strict-markers --strict-config"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E", "F", "W",       # pyflakes + pycodestyle
    "I",                  # isort
    "B",                  # bugbear（常见 bug）
    "UP",                 # pyupgrade
    "ASYNC",              # async 错误
    "S",                  # bandit 安全规则
    "RUF",                # ruff 自有
    "C90",                # mccabe 复杂度
]
ignore = [
    "S101",   # 测试里 assert 没问题
    "S105",   # 测试 fake 密码
    "S106",   # 测试 fake 密码（kwarg）
    "RUF001", # 中文项目: 字符串全角标点正常
    "RUF002", # 中文项目: docstring 全角标点正常
    "RUF003", # 中文项目: 注释全角标点正常
]
mccabe = { max-complexity = 10 }

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "S105", "S106", "S107"]
"scripts/*" = ["S603", "S607"]   # 脚本里允许 subprocess

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
warn_unused_ignores = true
disallow_untyped_defs = true
no_implicit_optional = true
warn_return_any = true
warn_redundant_casts = true
files = ["src"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false   # 测试允许略松

[tool.coverage.run]
source = ["src/ai_engine"]   # 路径相对 server/（pyproject.toml 与运行 cwd 都在 server/ 下）
omit = ["*/tests/*", "*/__main__.py"]
branch = true

[tool.coverage.report]
fail_under = 75       # MVP-1 至少 75%，逐 MVP 提高（MVP-2: 80%, MVP-3: 85%）
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

- [ ] **Step 2: 创建 `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
*.egg-info/
build/
dist/

# Env / secrets
.env
.env.*
!server/.env.example

# IDE
.idea/
.vscode/
*.swp

# Data
data/
ai_engine.db
ai_engine.db-shm
ai_engine.db-wal

# 代码镜像（Sourcegraph 自己管，无需进 git）
repos/

# Node
node_modules/
web/dist/
.vite/
```

- [ ] **Step 3: 创建 `.pre-commit-config.yaml`**

```yaml
default_language_version:
  python: python3.12

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic
          - pydantic-settings
          - types-aiofiles
        args: [server/src/]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: detect-private-key       # 防 .pem / .key 误提交

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks                  # 防密码 / API key 误提交

  - repo: local
    hooks:
      - id: conventional-commit-msg
        name: Conventional commit message format
        entry: scripts/check_commit_msg.sh
        language: script
        stages: [commit-msg]

      # 前端 lint / type-check（web/ 创建后启用，未创建时 files 不匹配自动跳过）
      - id: web-eslint
        name: web eslint
        entry: bash -c 'cd web && pnpm lint'
        language: system
        pass_filenames: false
        files: ^web/.*\.(ts|tsx|js)$
        require_serial: true

      - id: web-prettier
        name: web prettier
        entry: bash -c 'cd web && pnpm format:check'
        language: system
        pass_filenames: false
        files: ^web/.*\.(ts|tsx|js|json|css|md)$
        require_serial: true

      - id: web-typecheck
        name: web tsc --noEmit
        entry: bash -c 'cd web && pnpm typecheck'
        language: system
        pass_filenames: false
        files: ^web/.*\.(ts|tsx)$
        require_serial: true
```

- [ ] **Step 4: 创建 `.gitleaks.toml`**（用默认规则）

```toml
title = "Tevau AI Engine secret scanning"
# 默认规则即可。若需要白名单某些文件，在 [allowlist] 里配
[allowlist]
paths = [
    "server/.env.example",
    "server/tests/.+",   # 测试里的 fake key 不算
    "web/tests/.+",
]
```

- [ ] **Step 5: 创建 `scripts/check_commit_msg.sh`**

```bash
#!/usr/bin/env bash
# 校验 commit message 符合 Conventional Commits 格式
set -e

msg_file="$1"
[[ -z "$msg_file" ]] && { echo "usage: $0 <msg-file>"; exit 1; }

# 跳过 merge / revert / fixup 自动消息
first_line=$(head -n1 "$msg_file")
case "$first_line" in
    "Merge "*|"Revert "*|"fixup!"*|"squash!"*) exit 0 ;;
esac

pattern='^(feat|fix|refactor|test|docs|chore|perf|build|ci|style)(\([a-z0-9-]+\))?: .{1,72}$'
if [[ ! "$first_line" =~ $pattern ]]; then
    cat >&2 <<EOF
ERROR: commit message 不符合 Conventional Commits 格式

格式：  <type>(<scope>): <subject>
types:  feat | fix | refactor | test | docs | chore | perf | build | ci | style
scopes: mvp-1 | mvp-2 | mvp-3 | spec | plan | docs | engine | web | staff | db | prompt
长度:   subject ≤ 72 字符

示例:   feat(mvp-1): 添加 search_code 工具（Sourcegraph GraphQL）
       fix(engine): tool_router 漏注入 conversation_id
       docs(spec): §13.10 加 tawk.to 并存期

你的:   $first_line
EOF
    exit 1
fi
```

加可执行权限：
```bash
chmod +x scripts/check_commit_msg.sh
```

- [ ] **Step 6: 创建 `CONTRIBUTING.md`**

```markdown
# 贡献指南

## 工程规范基线

所有 commit 必须通过 pre-commit hook；CI 会再跑一遍。绕过 hook（`--no-verify`）一律拒收 PR。

## 安装

\`\`\`bash
uv pip install -e ".[dev]"
pre-commit install
pre-commit install --hook-type commit-msg
\`\`\`

## Commit 规范（Conventional Commits）

格式：\`<type>(<scope>): <subject>\`

- **types**: feat / fix / refactor / test / docs / chore / perf / build / ci / style
- **scopes**: mvp-1 / mvp-2 / mvp-3 / spec / plan / docs / engine / web / staff / db / prompt
- **subject** ≤ 72 字符，描述"做了什么"（祈使句、不用句号）
- 必要时 body 描述"为什么"

例：
\`\`\`
feat(mvp-1): 添加 search_code 工具（Sourcegraph GraphQL）
fix(engine): tool_router 漏注入 conversation_id（create_ticket 因此报错）
docs(spec): §13.10 加 tawk.to 并存期
\`\`\`

## 架构约束（违反者拒收 PR）

### 工具与数据安全（spec §2.3 / §4.2 / §5.4）

- ❌ 禁止在 \`query_*\` handler **外面**写自由 SQL
- ❌ 禁止用 f-string / % 拼接 SQL（必须参数化绑定 \`(%s, %s, ...)\`）
- ❌ 禁止绕过 \`tool_router\` 直接调工具 handler（破坏身份注入 + 审计）
- ✅ 所有 \`query_*\` 工具必须做工具层脱敏（手机/卡号/邮箱/规则名，见 spec §5.4）
- ✅ AI 工具 \`requires_subject_id=True\` 必须正确设置

### Prompt 与模型

- ❌ prompt 文件**绝不**出现具体人名（嘉豪 / 张三 / CTO 实名等）、内部规则名（R-217）、值班表
- ❌ 不在 .py 文件里硬编码 prompt 文本（所有 prompt 在 \`server/src/ai_engine/prompts/\` 下）
- ❌ 不在代码里硬编码模型 ID（通过 \`settings.default_model\` / \`settings.heavy_model\`）

### 代码结构

- 单文件 ≤ 300 行（超过强 warning，考虑拆分）
- 单函数 ≤ 80 行
- 圈复杂度 ≤ 10（ruff C90 强制）
- 严禁 \`from x import *\`
- 顶层 \`if __name__ == "__main__"\` 只在 \`scripts/\` 下出现

### 前端

- 单组件文件 ≤ 250 行（>250 拆 children）
- 不用 \`any\`（除非有 \`// eslint-disable-next-line\` 注释解释）
- 业务 fetch 必须封装在 \`web/src/api/\` 或 \`useXxx\` hooks 里，不在组件 inline

### 测试

- 每个 PR 至少包含一个新增/修改的测试
- 覆盖率 ≥ 75%（MVP-1）/ 80%（MVP-2）/ 85%（MVP-3）
- 测试不依赖外部网络（mock 所有外部调用：Anthropic / Sourcegraph / Lark / 事项中心 / GitLab）
- 数据库测试用 \`temp_db_url\` fixture（内存或临时文件）

### 密码与密钥

- ❌ **绝不**在任何 git 文件出现密码（gitleaks 自动拦）
- ❌ \`.env\` 必须在 \`.gitignore\`
- ✅ 测试用明确假值：\`sk-ant-test\` / \`mvp1-shared-secret\` / \`test-secret\`
- ✅ 真实密码只进本机 \`.env\` 或 vault

### Workflow

- 大改动先在 spec 改、确认设计、再开 plan task
- 不主动重构与当前 task 无关的代码
- 不主动合并 commit（每个 task 一个 commit，方便回滚）

## 跑全套检查

\`\`\`bash
make lint        # ruff check + ruff format --check
make typecheck   # mypy src
make test        # pytest 含覆盖率
make web-lint    # cd web && pnpm lint + pnpm typecheck
\`\`\`

CI 跑这四条 + e2e。
```

- [ ] **Step 7: 创建 `.gitlab-ci.yml`**

```yaml
stages: [lint, test, build]

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip
    - .mypy_cache
    - .ruff_cache

# ---- Python ----

py-lint:
  stage: lint
  image: python:3.12-slim
  script:
    - cd server
    - pip install -e ".[dev]"
    - ruff check src tests
    - ruff format --check src tests

py-typecheck:
  stage: lint
  image: python:3.12-slim
  script:
    - cd server
    - pip install -e ".[dev]"
    - mypy src

py-test:
  stage: test
  image: python:3.12-slim
  services:
    - name: mysql:8.0
      alias: mysql
      variables:
        MYSQL_ROOT_PASSWORD: rootpass
        MYSQL_DATABASE: unlimitpay_test
  script:
    - cd server
    - pip install -e ".[dev]"
    - pytest --cov=src/ai_engine --cov-report=term --cov-report=xml --cov-fail-under=75
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: server/coverage.xml      # pytest 在 server/ 下跑，coverage.xml 落在 server/

# ---- Frontend ----（web/ 在 Task 12 创建后开始跑）

web-lint:
  stage: lint
  image: node:20-alpine
  rules:
    - exists: [web/package.json]
  script:
    - cd web
    - corepack enable
    - pnpm install --frozen-lockfile
    - pnpm lint
    - pnpm typecheck

web-test:
  stage: test
  image: node:20-alpine
  rules:
    - exists: [web/package.json]
  script:
    - cd web
    - corepack enable
    - pnpm install --frozen-lockfile
    - pnpm test:ci   # 含 v8 coverage + thresholds 校验
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: web/coverage/cobertura-coverage.xml
```

- [ ] **Step 8: 初始化 pre-commit + 首次扫描**

```bash
# 后端依赖装在 server/
(cd server && uv pip install -e ".[dev]")
# pre-commit 在仓库根装
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit run --all-files
```

Expected: 第一次跑可能会有少量"trailing whitespace" / "end of file" 自动 fix；再跑一次应全绿。

- [ ] **Step 9: Commit**

```bash
git add server/pyproject.toml .gitignore .pre-commit-config.yaml .gitleaks.toml \
    scripts/check_commit_msg.sh CONTRIBUTING.md .gitlab-ci.yml
git commit -m "chore: Task 0 工程规范基线（ruff/mypy/pre-commit/CI/commit 规范/架构约束 + server/web 双子项目布局）"
```

> **后续要求**：每个 task 的 commit 必须用 Conventional Commits 格式，否则 pre-commit hook 直接拒绝。本 plan 后续所有 `git commit -m "..."` 已遵循此格式。

---
