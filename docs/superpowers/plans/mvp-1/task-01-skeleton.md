# Task 1: 项目骨架 + 配置加载

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- ~~Create: `server/pyproject.toml`~~ (已在 Task 0 创建)
- Create: `server/.env.example`
- Create: `Makefile`（顶层聚合，转发给 server/ 与 web/）
- Create: `README.md`
- Create: `server/src/ai_engine/__init__.py`
- Create: `server/src/ai_engine/config.py`
- Create: `server/tests/__init__.py`
- Create: `server/tests/test_config.py`

- [ ] **Step 1: ~~创建 `server/pyproject.toml`~~**

跳过——`server/pyproject.toml` 已在 Task 0 Step 1 创建为强化版（含完整依赖 + ruff strict + mypy strict + coverage ≥75%）。本 task 直接使用。

- [ ] **Step 2: 创建 `server/.env.example`**

```ini
# 必填
ANTHROPIC_API_KEY=sk-ant-xxx
# 公司自建 Claude 网关；走官方 API 时留空
ANTHROPIC_BASE_URL=https://awsclaude.tevaupay.com
DB_URL=sqlite+aiosqlite:///./ai_engine.db

# Sourcegraph 代码索引（MVP-1 自部署，见 docker-compose）
SOURCEGRAPH_URL=http://localhost:7080
SOURCEGRAPH_TOKEN=

# OpenAPI 文档（从 Apifox 项目导出的 OpenAPI 3.0 JSON）
OPENAPI_DOC_PATH=./repos/api-docs/openapi.json

# 可选
DEFAULT_MODEL=claude-sonnet-4-6
HEAVY_MODEL=claude-opus-4-7
PROMPTS_DIR=./src/ai_engine/prompts
LARK_WEBHOOK_URL=
EVENT_CENTER_URL=http://localhost:8000/_mock/event-center
EVENT_CENTER_SECRET=mvp1-shared-secret
MAX_TOOL_DEPTH=12
MAX_TOOL_RESULT_BYTES=262144
LOG_LEVEL=INFO
```

- [ ] **Step 3: 创建顶层 `Makefile`（聚合 server + web 命令）**

后端命令 `cd server` 后跑（pyproject / src / tests 都在 server/）；前端命令 `cd web` 后跑。这样 `make X` 在仓库根即可一键完成各端任务，不需要手动切目录。

```makefile
.PHONY: install hooks run test lint lint-fix format typecheck check \
        web-install web-dev web-build web-lint web-typecheck web-test

# ---- Backend (server/) ----

install:
	cd server && uv pip install -e ".[dev]"

hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

run:
	cd server && uvicorn ai_engine.main:app --reload --port 8000

test:
	cd server && pytest --cov=src/ai_engine --cov-report=term --cov-fail-under=75

lint:
	cd server && ruff check src tests
	cd server && ruff format --check src tests

lint-fix:
	cd server && ruff check --fix src tests
	cd server && ruff format src tests

format: lint-fix

typecheck:
	cd server && mypy src

check: lint typecheck test     # 一键跑全套（CI 等价）

# ---- Frontend (web/) ----

web-install:
	cd web && corepack enable && pnpm install

web-dev:
	cd web && pnpm dev

web-build:
	cd web && pnpm build

web-lint:
	cd web && pnpm lint
	cd web && pnpm format:check

web-typecheck:
	cd web && pnpm typecheck

web-test:
	cd web && pnpm test --run
```

- [ ] **Step 4: 创建 `README.md`**

```markdown
# Tevau 客服工单 AI 引擎 (MVP-1)

## 启动

1. 复制 `server/.env.example` 为 `.env`，填 `ANTHROPIC_API_KEY`
2. `make install`
3. `make run`（后端，默认 :8000）
4. `make web-install && make web-dev`（前端，默认 :5173）

## 测试

`make test`
```

- [ ] **Step 5: 创建 `server/src/ai_engine/__init__.py`（空文件）**

- [ ] **Step 6: 写 `server/tests/test_config.py`（先写失败测试）**

```python
import os
import pytest


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-sonnet-4-6")
    from ai_engine.config import settings

    settings.reload()
    assert settings.anthropic_api_key == "sk-ant-test"
    assert settings.default_model == "claude-sonnet-4-6"
    assert settings.max_tool_depth == 12


def test_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from pydantic import ValidationError

    from ai_engine.config import Settings

    with pytest.raises(ValidationError):   # 用具体异常避免 ruff B017
        Settings(_env_file=None)
```

- [ ] **Step 7: 跑一次确认失败**

```bash
(cd server && pytest tests/test_config.py -v)
```
Expected: ImportError / FAIL（config 还没写）

- [ ] **Step 8: 写 `server/src/ai_engine/config.py` 让测试过**

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = Field(...)
    anthropic_base_url: str | None = None  # 自建 Claude 网关; None 走官方 API（注释用半角标点避免 ruff RUF003）
    db_url: str = "sqlite+aiosqlite:///./ai_engine.db"
    default_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-7"
    sourcegraph_url: str = "http://localhost:7080"
    sourcegraph_token: str = ""
    openapi_doc_path: str = "./repos/api-docs/openapi.json"
    prompts_dir: str = "./src/ai_engine/prompts"
    lark_webhook_url: str | None = None
    event_center_url: str = "http://localhost:8000/_mock/event-center"
    event_center_secret: str = "mvp1-shared-secret"
    max_tool_depth: int = 12
    max_tool_result_bytes: int = 262_144
    log_level: str = "INFO"


_instance: Settings | None = None


class _SettingsProxy:
    def __getattr__(self, item: str) -> object:
        global _instance
        if _instance is None:
            _instance = Settings()  # type: ignore[call-arg]  # pydantic-settings 从 env 读
        return getattr(_instance, item)

    def reload(self) -> None:
        global _instance
        _instance = Settings()  # type: ignore[call-arg]  # pydantic-settings 从 env 读


settings = _SettingsProxy()
```

- [ ] **Step 9: 跑测试确认通过**

```bash
(cd server && pytest tests/test_config.py -v)
```
Expected: 2 passed

- [ ] **Step 10: Commit**

```bash
git init -q
git add server/pyproject.toml server/.env.example Makefile README.md \
    server/src/ai_engine/__init__.py server/src/ai_engine/config.py \
    server/tests/__init__.py server/tests/test_config.py
git commit -m "feat: 项目骨架 + 配置加载"
```

---
