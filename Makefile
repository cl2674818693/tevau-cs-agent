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
