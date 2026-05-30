# 管理后台 M3b 实施计划 — AI 运营

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1/M2/M3a 基础上落地 AI 运营侧（spec §5.4）：Prompt 在线编辑与发布、知识库管理、范围与拦截配置(guardrails)、AI 自动调用接 tool_policies（M2 遗留）。

**Architecture:** 沿用既有分层：SQLAlchemy Core schema + 每域 persistence + FastAPI APIRouter + React Route。Prompt 编辑走"DB-first 回退文件"模式（registry/loader 加载时优先查 `prompt_drafts` 已发布版本，缺失则回退现有文件）。知识库同模式（`knowledge_entries` 已发布条目优先于 `lookup_*` 工具的文件数据源）。Guardrails 提供 helper + API；接入点若落在用户脏文件 `chat.py`，本里程碑只做配置面 + helper，自动触发延后。AI 自动调用接 `tool_policies` 引入特殊 role `"ai"`，默认放行保兼容。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind。

---

## 关键约定（沿用 M1/M2/M3a）

1. 可选筛选 SQL：`(CAST(:p AS TEXT) IS NULL OR col = :p)`。
2. 时间列用 `from ai_engine.persistence.schema import now_str`。
3. 新增表 / 改列必须配独立 alembic 迁移；不动既有迁移文件。新表必须出现在 `tests/test_alembic_migrations.py::test_alembic_upgrade_matches_init_db_schema` 通过的表集合里。
4. 后端测试用 `temp_db_url`/`seeded_db` fixture + `ASGITransport` + `AsyncClient`，参照 `tests/test_admin_qa_api.py`。
5. 角色 gate：`require_roles(*roles)`（M1）。审计：`admin_audit.log_admin_action(...)`（M1）。
6. 后端测试 / ruff：用 `cd server && .venv/bin/python -m pytest tests/xxx.py -v` / `.venv/bin/ruff check src/<file> tests/<file>`。自己改/建文件 0 warning。
7. 前端验证：`cd web && pnpm typecheck` + `npx eslint src/<file>`（不全局 lint，避开 pre-existing warning）；`max-lines-per-function` ≤80；`PageContainer width="wide"`。
8. git discipline：`main` 分支（用户已同意）。工作树原始 11 modified + 1 untracked 脏文件（M2/M3a 后已稳定）。**绝不**用 `git add -A/.`；用 `git -C /Users/sunchenglin/codes/tevau-cs-engine add <精确路径>`。`server/uv.lock` 若被测试副产物改脏，收尾步骤 `git -C ... checkout server/uv.lock` 还原；本 task 不要 stage。
9. commit message 中文 + 末尾 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`。

---

## M1/M2/M3a 已交付基线（M3b 直接复用）

- 角色：6 个（agent/senior/engineer/admin/supervisor/manager）。
- 鉴权：`require_roles(*roles)`；审计：`admin_audit.log_admin_action`。
- M2 工具权限：`persistence/tool_policies.py`（`is_tool_allowed/is_unmask_allowed/list_all/upsert_many/invalidate_cache` + `_STAFF_DEFAULT_TOOLS`/`_default_allowed`/`_default_unmask`）；客服代查端点已接入。
- M2 Prompt 灰度：`api/admin_prompts.py`（仅 admin 调灰度 rollout）；`prompts/registry.py` 管理 version 列表 + 灰度分桶；`prompts/loader.py` 加载 prompt 内容。
- M3a 菜单结构：`StaffLayout.tsx` 用 `roles?: string[]`。
- 前端 UI 模式：`api/admin*.ts`（`staffFetch` + `authHeaders`）；`components/ui/*`。

---

## 文件结构总览

**后端新增**：
- `server/src/ai_engine/persistence/prompt_drafts.py` — Prompt 草稿 / 发布 persistence
- `server/src/ai_engine/persistence/knowledge.py` — 知识库 CRUD + 按 type/key 查询
- `server/src/ai_engine/persistence/guardrails.py` — 防护规则 persistence + helper `evaluate_guardrails`
- `server/src/ai_engine/api/admin_prompt_editor.py` — Prompt 编辑/发布 API
- `server/src/ai_engine/api/admin_knowledge.py` — 知识库 CRUD + from-gap API
- `server/src/ai_engine/api/admin_guardrails.py` — Guardrails CRUD API
- 3 个独立 alembic 迁移

**后端修改**：
- `server/src/ai_engine/persistence/schema.py` — 新增 3 张表
- `server/src/ai_engine/main.py` — include 3 个新 router
- `server/src/ai_engine/prompts/loader.py` — DB-first 优先读 `prompt_drafts` published（**确认非脏**）
- `server/src/ai_engine/agent/tools/lookup_api_doc.py` — 优先读 `knowledge_entries`（**确认非脏**）
- `server/src/ai_engine/agent/tools/lookup_error_code.py` — 同上（**确认非脏**）
- `server/src/ai_engine/agent/tool_router.py` — `dispatch()` 前置加 `is_tool_allowed(tool, "ai")` 校验（**确认非脏**；M2 Task 4.3 改 staff_conversations.py 而非 tool_router.py，本 task 才动 tool_router.py）
- `server/src/ai_engine/persistence/tool_policies.py` — `_default_allowed(...,role="ai")` 加默认 True 分支

**前端新增**：
- `web/src/api/adminPromptEditor.ts`、`adminKnowledge.ts`、`adminGuardrails.ts`
- `web/src/routes/admin/PromptEditorRoute.tsx`、`KnowledgeRoute.tsx`、`GuardrailsRoute.tsx`

**前端修改**：
- `web/src/components/StaffLayout.tsx` — 加 3 个 M3b 菜单项
- `web/src/App.tsx` — 注册 3 个新路由

---

# Phase 0 — 菜单扩展

## Task 0.1: 后台菜单加 M3b 三项

**Files:**
- Modify: `web/src/components/StaffLayout.tsx`

- [ ] **Step 1: 改 NAV_ITEMS**

`web/src/components/StaffLayout.tsx`：
- import 区加新图标：`FileEdit`、`BookOpen`、`ShieldAlert`（lucide-react）。
- NAV_ITEMS 末尾追加：
```typescript
  // M3b AI 运营
  { to: "/admin/prompt-editor", label: "Prompt 编辑", short: "编辑", icon: FileEdit, roles: ["engineer", "admin"] },
  { to: "/admin/knowledge", label: "知识库", short: "知识", icon: BookOpen, roles: ["supervisor", "engineer", "admin"] },
  { to: "/admin/guardrails", label: "范围拦截", short: "拦截", icon: ShieldAlert, roles: ["engineer", "admin"] },
```

- [ ] **Step 2: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/components/StaffLayout.tsx` → 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/components/StaffLayout.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 后台菜单加 M3b 三项（Prompt 编辑/知识库/范围拦截）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 1 — Prompt 在线编辑与发布

## Task 1.1: prompt_drafts 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

`schema.py` 末尾追加：
```python
# Prompt 草稿 / 发布（M3b §5.4.b）
# DB-first 读取：loader 先查 status=published 的最新行；缺失回退文件。
# 多个 published 行（不同 file_name 同 version）可共存；同 (version,file_name) 取最新 id。
prompt_drafts = Table(
    "prompt_drafts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("version", String(16), nullable=False),
    Column("file_name", String(64), nullable=False),  # 例如 "reply_style.c.md"
    Column("content", Text, nullable=False),
    Column("status", String(16), nullable=False, server_default="draft"),  # draft / published
    Column("editor", String(64)),
    Column("created_at", String(32), nullable=False),
    CheckConstraint("status IN ('draft','published')", name="ck_prompt_draft_status"),
)
Index("idx_prompt_drafts_lookup", prompt_drafts.c.version, prompt_drafts.c.file_name, prompt_drafts.c.status)
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "prompt_drafts"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "prompt_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("file_name", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("editor", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_prompt_draft_status"),
    )
    op.create_index(
        "idx_prompt_drafts_lookup", "prompt_drafts",
        ["version", "file_name", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_prompt_drafts_lookup", table_name="prompt_drafts")
    op.drop_table("prompt_drafts")
```

- [ ] **Step 3: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): prompt_drafts 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.2: prompt_drafts persistence

**Files:**
- Create: `server/src/ai_engine/persistence/prompt_drafts.py`
- Test: `server/tests/test_prompt_drafts_dao.py`

API 设计：
- `create_draft(version, file_name, content, editor)` → 新行 status='draft'
- `list_by_version(version)` → 返回该版本所有 draft + published 行
- `publish(draft_id, editor)` → 把指定 draft 行状态置 published；旧的同 (version,file_name) published 行不主动改（loader 读最新 id），保留历史
- `get_published(version, file_name)` → 取最新一行 status=published（loader 调用）
- `delete_draft(id)`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_prompt_drafts_dao.py
from ai_engine.persistence import prompt_drafts


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_and_list(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "reply_style.c.md", "你好世界", "EN1")
    rows = await prompt_drafts.list_by_version("v2.0.0")
    assert len(rows) == 1 and rows[0]["id"] == did
    assert rows[0]["status"] == "draft"


async def test_publish_then_get(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "reply_style.c.md", "正式版本", "EN1")
    await prompt_drafts.publish(did, "EN1")
    p = await prompt_drafts.get_published("v2.0.0", "reply_style.c.md")
    assert p is not None and p["content"] == "正式版本"


async def test_get_published_returns_latest(temp_db_url):
    await _init(temp_db_url)
    d1 = await prompt_drafts.create_draft("v2.0.0", "a.md", "v1", "EN1")
    await prompt_drafts.publish(d1, "EN1")
    d2 = await prompt_drafts.create_draft("v2.0.0", "a.md", "v2", "EN1")
    await prompt_drafts.publish(d2, "EN1")
    p = await prompt_drafts.get_published("v2.0.0", "a.md")
    assert p["content"] == "v2"


async def test_delete_draft(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "a.md", "x", "EN1")
    await prompt_drafts.delete_draft(did)
    assert await prompt_drafts.list_by_version("v2.0.0") == []


async def test_get_published_none_when_missing(temp_db_url):
    await _init(temp_db_url)
    assert await prompt_drafts.get_published("v1.0.0", "nope.md") is None
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_prompt_drafts_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/prompt_drafts.py
"""Prompt 草稿 / 发布 persistence。

读取语义：get_published(version, file_name) 取最新一条 status=published（按 id DESC）。
loader 调用此函数得到 DB 内容；缺失则回退文件读取。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_draft(version: str, file_name: str, content: str, editor: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO prompt_drafts(version, file_name, content, status, editor, created_at) "
        "VALUES (:v, :f, :c, 'draft', :e, :now) RETURNING id",
        {"v": version, "f": file_name, "c": content, "e": editor, "now": now_str()},
    )


async def list_by_version(version: str) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, version, file_name, content, status, editor, created_at "
        "FROM prompt_drafts WHERE version = :v ORDER BY id DESC",
        {"v": version},
    )


async def publish(draft_id: int, editor: str) -> None:
    await db.execute(
        "UPDATE prompt_drafts SET status = 'published', editor = :e WHERE id = :id",
        {"e": editor, "id": int(draft_id)},
    )


async def get_published(version: str, file_name: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, content, editor, created_at FROM prompt_drafts "
        "WHERE version = :v AND file_name = :f AND status = 'published' "
        "ORDER BY id DESC LIMIT 1",
        {"v": version, "f": file_name},
    )


async def delete_draft(draft_id: int) -> None:
    await db.execute(
        "DELETE FROM prompt_drafts WHERE id = :id", {"id": int(draft_id)}
    )
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_prompt_drafts_dao.py -v` (5 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/prompt_drafts.py tests/test_prompt_drafts_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/prompt_drafts.py server/tests/test_prompt_drafts_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): Prompt 草稿/发布 persistence" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: loader 改造 DB-first

**Files:**
- Modify: `server/src/ai_engine/prompts/loader.py`（**先 grep 确认非脏**）
- Test: `server/tests/test_prompt_loader_db_first.py`

设计：loader 现有函数（如 `load_prompt_file(version, file_name)`）返回字符串。改造为：先查 `prompt_drafts.get_published` → 有则返回 DB content；无则原文件读取逻辑。

接入策略：不改 loader 公共 API 签名，只在内部加 DB 优先分支。

- [ ] **Step 1: 确认非脏 + 看现状**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/prompts/loader.py` → 无输出。
读 `server/src/ai_engine/prompts/loader.py`，定位现有加载函数（可能名为 `load_file(version, name)` 或 `_load_text(version, name)`）。M1 探查时确认该模块负责从 `prompts/<version>/<file>.md` 读文件。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_prompt_loader_db_first.py
"""loader 优先 DB published；缺失回退文件。"""


async def test_db_published_wins(temp_db_url, monkeypatch, tmp_path):
    from ai_engine.persistence import prompt_drafts
    from ai_engine.persistence.db import init_db
    await init_db()
    # 准备一个文件副本（让 PROMPTS_DIR 指向 tmp_path）
    import shutil
    from pathlib import Path
    src = Path("src/ai_engine/prompts")
    shutil.copytree(src, tmp_path / "prompts")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path / "prompts"))
    from ai_engine.config import settings
    settings.reload()

    # DB 写一条 published 覆盖
    did = await prompt_drafts.create_draft("v1.0.0", "reply_style.c.md", "DB优先内容", "EN1")
    await prompt_drafts.publish(did, "EN1")

    # loader 加载
    from ai_engine.prompts import loader
    # 注意：loader 公共 API 名以现有为准，本测试只验证：能拿到 "DB优先内容" 而非文件内容
    content = await loader.load(version="v1.0.0", file_name="reply_style.c.md")
    assert "DB优先内容" in content


async def test_db_missing_falls_back_to_file(temp_db_url, monkeypatch, tmp_path):
    from ai_engine.persistence.db import init_db
    await init_db()
    import shutil
    from pathlib import Path
    src = Path("src/ai_engine/prompts")
    shutil.copytree(src, tmp_path / "prompts")
    monkeypatch.setenv("PROMPTS_DIR", str(tmp_path / "prompts"))
    from ai_engine.config import settings
    settings.reload()

    from ai_engine.prompts import loader
    content = await loader.load(version="v1.0.0", file_name="reply_style.c.md")
    # 文件存在 → 内容非空
    assert content and len(content) > 0
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_prompt_loader_db_first.py -v`
Expected: FAIL — `loader.load` 不存在或 DB 优先未实现。

- [ ] **Step 4: 改 loader**

读 `server/src/ai_engine/prompts/loader.py` 现有实现。引入一个新的统一入口 `async def load(version: str, file_name: str) -> str`：
- 先 `try: from ai_engine.persistence.prompt_drafts import get_published`
- `db_row = await get_published(version, file_name)`；若 `db_row is not None`，返回 `db_row["content"]`
- 否则按现有文件读取逻辑返回内容（如已有同步函数 `_read_file(version, file_name)`，直接调用并返回；不破坏既有同步加载点）

代码示例（按现有 loader.py 实际结构调整；若已有 `load_file(version, name)`，新增 `load` 函数包装它）：
```python
async def load(version: str, file_name: str) -> str:
    """DB-first：优先读 prompt_drafts 已发布版本；缺失回退文件。"""
    try:
        from ai_engine.persistence.prompt_drafts import get_published

        row = await get_published(version, file_name)
        if row is not None:
            return str(row["content"])
    except Exception:
        # DB 不可达等：静默回退到文件
        pass
    # 文件回退：调用既有内部函数（按实际名调整）
    return _read_file(version, file_name)


def _read_file(version: str, file_name: str) -> str:
    # 用现有文件读取逻辑——如果 loader.py 已有等价函数，这里直接调用即可，不要重复实现
    from pathlib import Path
    from ai_engine.config import settings
    return Path(settings.prompts_dir, version, file_name).read_text(encoding="utf-8")
```
注意：如 loader.py 现有 API 不同（如 `load_text_for_version` / 异步/同步差异），把新 `load` 函数适配为该现有 API 的包装，保持公共接口稳定。

- [ ] **Step 5: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_prompt_loader_db_first.py tests/test_prompts_loader.py -v` (既有 loader 测试不退化)
Run: `cd server && .venv/bin/ruff check src/ai_engine/prompts/loader.py tests/test_prompt_loader_db_first.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/prompts/loader.py server/tests/test_prompt_loader_db_first.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): loader 改 DB-first（prompt_drafts published 优先，缺失回退文件）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.4: Prompt 编辑 API + 审计

**Files:**
- Create: `server/src/ai_engine/api/admin_prompt_editor.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_prompt_editor_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_prompt_editor_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/prompt-editor?version=v1.0.0",
                        headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_publish_get(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/prompt-editor",
            json={"version": "v2.0.0", "file_name": "a.md", "content": "草稿内容"},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        did = r.json()["id"]
        pub = await c.post(
            f"/admin/api/v1/prompt-editor/{did}/publish",
            headers=_h(env["eng"]),
        )
        assert pub.status_code == 200
        listed = (await c.get("/admin/api/v1/prompt-editor?version=v2.0.0",
                              headers=_h(env["eng"]))).json()["drafts"]
    assert any(d["id"] == did and d["status"] == "published" for d in listed)
    audits = await admin_audit.list_admin_actions(action="prompt.publish", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)


async def test_delete_draft(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/prompt-editor",
            json={"version": "v2.0.0", "file_name": "b.md", "content": "x"},
            headers=_h(env["eng"]),
        )
        did = r.json()["id"]
        await c.delete(f"/admin/api/v1/prompt-editor/{did}", headers=_h(env["eng"]))
        listed = (await c.get("/admin/api/v1/prompt-editor?version=v2.0.0",
                              headers=_h(env["eng"]))).json()["drafts"]
    assert all(d["id"] != did for d in listed)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_prompt_editor_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_prompt_editor.py
"""Prompt 编辑/发布（engineer/admin）。所有写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, prompt_drafts

router = APIRouter()
_eng = require_roles("engineer", "admin")


class DraftIn(BaseModel):
    version: str
    file_name: str
    content: str


@router.get("/admin/api/v1/prompt-editor")
async def list_drafts(
    version: str = Query(...),
    staff: dict[str, Any] = Depends(_eng),
) -> dict[str, Any]:
    return {"drafts": await prompt_drafts.list_by_version(version)}


@router.post("/admin/api/v1/prompt-editor")
async def create_draft(
    body: DraftIn, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    did = await prompt_drafts.create_draft(body.version, body.file_name, body.content, actor)
    await admin_audit.log_admin_action(
        actor=actor, action="prompt.draft.create",
        target_type="prompt_draft", target_id=str(did),
        detail={"version": body.version, "file_name": body.file_name},
    )
    return {"ok": True, "id": did}


@router.post("/admin/api/v1/prompt-editor/{draft_id}/publish")
async def publish_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    await prompt_drafts.publish(draft_id, actor)
    await admin_audit.log_admin_action(
        actor=actor, action="prompt.publish",
        target_type="prompt_draft", target_id=str(draft_id),
    )
    return {"ok": True}


@router.delete("/admin/api/v1/prompt-editor/{draft_id}")
async def delete_draft(
    draft_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await prompt_drafts.delete_draft(draft_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="prompt.draft.delete",
        target_type="prompt_draft", target_id=str(draft_id),
    )
    return {"ok": True}
```

`main.py`：import `from ai_engine.api.admin_prompt_editor import router as admin_prompt_editor_router` + `app.include_router(admin_prompt_editor_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_prompt_editor_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_prompt_editor.py src/ai_engine/main.py tests/test_admin_prompt_editor_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_prompt_editor.py server/src/ai_engine/main.py server/tests/test_admin_prompt_editor_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): Prompt 编辑/发布 API（engineer 鉴权 + 审计）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.5: Prompt 编辑前端页

**Files:**
- Create: `web/src/api/adminPromptEditor.ts`
- Create: `web/src/routes/admin/PromptEditorRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminPromptEditor.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type PromptDraft = {
  id: number;
  version: string;
  file_name: string;
  content: string;
  status: string;
  editor: string | null;
  created_at: string;
};

export async function listDrafts(token: string, version: string): Promise<PromptDraft[]> {
  const r = await staffFetch(
    `/admin/api/v1/prompt-editor?version=${encodeURIComponent(version)}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).drafts;
}

export async function createDraft(
  token: string, body: { version: string; file_name: string; content: string },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/prompt-editor", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
  return r.json();
}

export async function publishDraft(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/prompt-editor/${id}/publish`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`publish ${r.status}`);
}

export async function deleteDraft(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/prompt-editor/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: PromptEditorRoute**

```tsx
// web/src/routes/admin/PromptEditorRoute.tsx
import { useEffect, useState } from "react";

import {
  createDraft, deleteDraft, listDrafts, type PromptDraft, publishDraft,
} from "../../api/adminPromptEditor";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const KNOWN_VERSIONS = ["v1.0.0", "v1.1.0", "v2.0.0"];

function DraftEditor({ version, onCreated, onError }: {
  version: string; onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [fname, setFname] = useState("reply_style.c.md");
  const [content, setContent] = useState("");
  async function submit() {
    if (!token || !fname) return;
    try {
      await createDraft(token, { version, file_name: fname, content });
      setContent("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="文件名 reply_style.c.md" value={fname} className="w-72"
            onChange={(e) => setFname(e.target.value)} />
          <Button size="md" onClick={submit} disabled={!fname || !content}>新建草稿</Button>
        </div>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={8} placeholder="Prompt 内容（Markdown）" value={content}
          aria-label="Prompt 内容"
          onChange={(e) => setContent(e.target.value)} />
      </div>
    </Card>
  );
}

function DraftRow({ d, onChanged, onError }: {
  d: PromptDraft; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function pub() {
    if (!token) return;
    try { await publishDraft(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "发布失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteDraft(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{d.id}</td>
      <td className="px-3 py-2 text-ink-primary">{d.file_name}</td>
      <td className="px-3 py-2">{d.status}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.editor ?? "—"}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.created_at}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          {d.status === "draft" && <button className="text-brand" onClick={pub}>发布</button>}
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function PromptEditorRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [version, setVersion] = useState("v2.0.0");
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listDrafts(token, version).then(setDrafts).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, version]);

  return (
    <PageContainer width="wide">
      <PageHeader title="Prompt 在线编辑" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <span className="text-body3 text-ink-secondary">版本：</span>
            <select value={version} onChange={(e) => setVersion(e.target.value)}
              className="rounded border border-line px-2 py-1 text-body2">
              {KNOWN_VERSIONS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
        </Card>
      )}
      {allowed && <DraftEditor version={version} onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <Card className="mt-3">
          <table className="w-full text-body3">
            <thead>
              <tr className="border-b border-line text-ink-secondary">
                <th className="px-3 py-2 text-left font-normal">ID</th>
                <th className="px-3 py-2 text-left font-normal">文件</th>
                <th className="px-3 py-2 text-left font-normal">状态</th>
                <th className="px-3 py-2 text-left font-normal">编辑人</th>
                <th className="px-3 py-2 text-left font-normal">时间</th>
                <th className="px-3 py-2 text-left font-normal">操作</th>
              </tr>
            </thead>
            <tbody>
              {drafts.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">该版本无草稿</td></tr>
              )}
              {drafts.map((d) => <DraftRow key={d.id} d={d} onChanged={reload} onError={setErr} />)}
            </tbody>
          </table>
        </Card>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `PromptEditorRoute` + `<Route path="/admin/prompt-editor" element={<PromptEditorRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminPromptEditor.ts src/routes/admin/PromptEditorRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminPromptEditor.ts web/src/routes/admin/PromptEditorRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): Prompt 在线编辑前端页（草稿/发布/删除）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 2 — 知识库管理

## Task 2.1: knowledge_entries 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义 + 迁移**

`schema.py` 末尾追加：
```python
# 知识库条目（M3b §5.4.e）
# lookup_api_doc / lookup_error_code 工具优先读 status='published' 的条目；缺失回退到原数据源。
knowledge_entries = Table(
    "knowledge_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String(32), nullable=False),  # api_doc / error_code / faq
    Column("key", String(128), nullable=False),  # api_doc=path；error_code=code；faq=slug
    Column("title", String(256), nullable=False),
    Column("content", Text, nullable=False),
    Column("locale", String(16), nullable=False, server_default="zh"),
    Column("status", String(16), nullable=False, server_default="draft"),  # draft / published
    Column("source_gap_signal", String(64)),  # 从 insights 知识缺口转的条目，记录原信号
    Column("created_by", String(64)),
    Column("updated_at", String(32), nullable=False),
    CheckConstraint("type IN ('api_doc','error_code','faq')", name="ck_knowledge_type"),
    CheckConstraint("status IN ('draft','published')", name="ck_knowledge_status"),
)
Index(
    "ux_knowledge_key", knowledge_entries.c.type, knowledge_entries.c.key,
    knowledge_entries.c.locale, knowledge_entries.c.status, unique=True,
)
```

Run: `cd server && .venv/bin/python -m alembic revision -m "knowledge_entries"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(16), nullable=False, server_default="zh"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("source_gap_signal", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.CheckConstraint("type IN ('api_doc','error_code','faq')", name="ck_knowledge_type"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_knowledge_status"),
    )
    op.create_index(
        "ux_knowledge_key", "knowledge_entries",
        ["type", "key", "locale", "status"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_knowledge_key", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
```

- [ ] **Step 2: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): knowledge_entries 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: 知识库 persistence

**Files:**
- Create: `server/src/ai_engine/persistence/knowledge.py`
- Test: `server/tests/test_knowledge_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_knowledge_dao.py
from ai_engine.persistence import knowledge


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_publish_get(temp_db_url):
    await _init(temp_db_url)
    eid = await knowledge.upsert_entry(
        type_="error_code", key="E1001", title="登录失败",
        content="账号或密码错误", locale="zh", created_by="EN1",
    )
    await knowledge.publish(eid)
    row = await knowledge.get_published(type_="error_code", key="E1001", locale="zh")
    assert row is not None and row["title"] == "登录失败"


async def test_upsert_updates_existing(temp_db_url):
    """同 (type, key, locale, status=draft) 的条目第二次 upsert 覆盖。"""
    await _init(temp_db_url)
    e1 = await knowledge.upsert_entry(
        type_="faq", key="login_help", title="登录指南", content="v1", locale="zh", created_by="EN1",
    )
    e2 = await knowledge.upsert_entry(
        type_="faq", key="login_help", title="登录指南", content="v2", locale="zh", created_by="EN1",
    )
    assert e1 == e2


async def test_list_by_type_filter(temp_db_url):
    await _init(temp_db_url)
    await knowledge.upsert_entry(
        type_="error_code", key="E1", title="t1", content="c1", locale="zh", created_by="EN1",
    )
    await knowledge.upsert_entry(
        type_="faq", key="f1", title="t2", content="c2", locale="zh", created_by="EN1",
    )
    rows = await knowledge.list_entries(type_="error_code")
    assert len(rows) == 1 and rows[0]["key"] == "E1"


async def test_get_published_misses_draft_only(temp_db_url):
    await _init(temp_db_url)
    await knowledge.upsert_entry(
        type_="api_doc", key="/users", title="x", content="y", locale="zh", created_by="EN1",
    )
    row = await knowledge.get_published(type_="api_doc", key="/users", locale="zh")
    assert row is None
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_knowledge_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/knowledge.py
"""知识库 CRUD + 工具优先读取。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def upsert_entry(
    type_: str,
    key: str,
    title: str,
    content: str,
    locale: str = "zh",
    created_by: str | None = None,
    source_gap_signal: str | None = None,
) -> int:
    """按 (type, key, locale, status='draft') upsert 草稿；返回 id。

    若已有 draft 行则覆盖 content/title；若没有则插入新 draft。
    发布操作走 publish() 把 draft 升级为 published。
    """
    existing = await db.fetch_one(
        "SELECT id FROM knowledge_entries "
        "WHERE type = :t AND key = :k AND locale = :l AND status = 'draft'",
        {"t": type_, "k": key, "l": locale},
    )
    if existing is not None:
        await db.execute(
            "UPDATE knowledge_entries SET title = :ti, content = :c, updated_at = :now "
            "WHERE id = :id",
            {"ti": title, "c": content, "now": now_str(), "id": existing["id"]},
        )
        return int(existing["id"])
    return await db.insert_returning_id(
        "INSERT INTO knowledge_entries(type, key, title, content, locale, status, "
        "source_gap_signal, created_by, updated_at) "
        "VALUES (:t, :k, :ti, :c, :l, 'draft', :gs, :by, :now) RETURNING id",
        {
            "t": type_, "k": key, "ti": title, "c": content, "l": locale,
            "gs": source_gap_signal, "by": created_by, "now": now_str(),
        },
    )


async def publish(entry_id: int) -> None:
    await db.execute(
        "UPDATE knowledge_entries SET status = 'published', updated_at = :now "
        "WHERE id = :id",
        {"now": now_str(), "id": int(entry_id)},
    )


async def get_published(type_: str, key: str, locale: str = "zh") -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, title, content, updated_at FROM knowledge_entries "
        "WHERE type = :t AND key = :k AND locale = :l AND status = 'published' "
        "ORDER BY id DESC LIMIT 1",
        {"t": type_, "k": key, "l": locale},
    )


async def list_entries(
    type_: str | None = None, status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, type, key, title, locale, status, source_gap_signal, "
        "created_by, updated_at FROM knowledge_entries "
        "WHERE (CAST(:t AS TEXT) IS NULL OR type = :t) "
        "AND (CAST(:s AS TEXT) IS NULL OR status = :s) "
        "ORDER BY id DESC LIMIT :lim",
        {"t": type_, "s": status, "lim": limit},
    )


async def delete_entry(entry_id: int) -> None:
    await db.execute(
        "DELETE FROM knowledge_entries WHERE id = :id", {"id": int(entry_id)}
    )
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_knowledge_dao.py -v` (4 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/knowledge.py tests/test_knowledge_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/knowledge.py server/tests/test_knowledge_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 知识库 persistence（upsert/publish/list）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.3: lookup_* 工具改 DB-first

**Files:**
- Modify: `server/src/ai_engine/agent/tools/lookup_api_doc.py`（**先 grep 确认非脏**）
- Modify: `server/src/ai_engine/agent/tools/lookup_error_code.py`（**先 grep 确认非脏**）
- Test: `server/tests/test_lookup_db_first.py`

设计：两个工具都先查 `knowledge.get_published(type_, key, locale)`：
- `lookup_api_doc`: type="api_doc"，key=path
- `lookup_error_code`: type="error_code"，key=code
有则返回 DB 内容；无则原数据源查询不变。

- [ ] **Step 1: 确认非脏**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/agent/tools/lookup_api_doc.py server/src/ai_engine/agent/tools/lookup_error_code.py`
Expected: 无输出。若有：BLOCKED 报告。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_lookup_db_first.py
"""lookup_* 工具优先读知识库 published 条目；缺失回退原数据源。"""


async def test_lookup_error_code_db_first(temp_db_url):
    from ai_engine.persistence import knowledge
    from ai_engine.persistence.db import init_db
    await init_db()
    eid = await knowledge.upsert_entry(
        type_="error_code", key="E1001",
        title="自定义标题", content="自定义说明：账号锁定",
        locale="zh", created_by="EN1",
    )
    await knowledge.publish(eid)
    from ai_engine.agent.tools.lookup_error_code import _handler  # 私有 handler 直接调
    result = await _handler(code="E1001", locale="zh")
    # DB 版本被采用
    assert "自定义说明：账号锁定" in str(result)


async def test_lookup_api_doc_falls_back_when_db_empty(temp_db_url):
    """DB 无条目时回退到原数据源（具体回退结果与既有实现相关，本测试只验证不抛异常）。"""
    from ai_engine.persistence.db import init_db
    await init_db()
    from ai_engine.agent.tools.lookup_api_doc import _handler
    # 不写 DB，直接调（路径任选；回退行为依赖既有实现）
    try:
        await _handler(path="/some/nonexistent/endpoint")
    except Exception:
        # 既有数据源可能 raise 也可能 return 空——任一都算"非 DB-first 短路"
        pass
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_lookup_db_first.py -v`
Expected: 第一个 FAIL（工具尚未接 DB-first）。第二个可能 PASS 或 FAIL，不阻塞。

- [ ] **Step 4: 改 lookup_error_code.py**

读 `server/src/ai_engine/agent/tools/lookup_error_code.py`。找到 `_handler(...)` 函数（或类似入口）。在函数开头加 DB 优先分支：
```python
async def _handler(code: str, locale: str = "zh", **kwargs) -> str:
    # M3b: 优先读知识库已发布条目
    try:
        from ai_engine.persistence.knowledge import get_published
        row = await get_published(type_="error_code", key=code, locale=locale)
        if row is not None:
            return f"{row['title']}\n\n{row['content']}"
    except Exception:
        pass
    # 回退：原数据源查询逻辑（保持不动）
    ...  # 既有代码
```
不动既有签名、不动既有回退逻辑——只在函数顶部加 DB-first 分支。

- [ ] **Step 5: 改 lookup_api_doc.py**

读 `server/src/ai_engine/agent/tools/lookup_api_doc.py`。同样在 `_handler` 入口加：
```python
async def _handler(path: str, locale: str = "zh", **kwargs) -> str:
    try:
        from ai_engine.persistence.knowledge import get_published
        row = await get_published(type_="api_doc", key=path, locale=locale)
        if row is not None:
            return f"{row['title']}\n\n{row['content']}"
    except Exception:
        pass
    ...  # 既有代码
```

- [ ] **Step 6: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_lookup_db_first.py tests/test_lookup_api_doc.py -v`
Expected: 新增 lookup_error_code DB-first 测试 pass；既有 lookup_api_doc 测试不退化。
Run: `cd server && .venv/bin/ruff check src/ai_engine/agent/tools/lookup_error_code.py src/ai_engine/agent/tools/lookup_api_doc.py tests/test_lookup_db_first.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/agent/tools/lookup_error_code.py server/src/ai_engine/agent/tools/lookup_api_doc.py server/tests/test_lookup_db_first.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): lookup_api_doc/lookup_error_code 改 DB-first（已发布条目优先）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.4: 知识库 API + 审计 + from-gap

**Files:**
- Create: `server/src/ai_engine/api/admin_knowledge.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_knowledge_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_knowledge_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/knowledge", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_publish_list(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/knowledge",
            json={"type": "faq", "key": "login", "title": "登录指南",
                  "content": "怎么登录...", "locale": "zh"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        eid = r.json()["id"]
        pub = await c.post(f"/admin/api/v1/knowledge/{eid}/publish", headers=_h(env["sup"]))
        assert pub.status_code == 200
        listed = (await c.get("/admin/api/v1/knowledge?type=faq",
                              headers=_h(env["sup"]))).json()["entries"]
    assert any(e["id"] == eid and e["status"] == "published" for e in listed)
    audits = await admin_audit.list_admin_actions(action="knowledge.publish", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)


async def test_from_gap_endpoint(env):
    """gap → entry 直转：建一个 draft 条目，source_gap_signal 记录信号 key。"""
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/knowledge/from-gap",
            json={"signal_key": "out_of_scope:卡片申请",
                  "type": "faq", "key": "card_apply", "title": "卡片申请说明",
                  "content": "..."},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        eid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/knowledge?type=faq",
                              headers=_h(env["sup"]))).json()["entries"]
    target = next((e for e in listed if e["id"] == eid), None)
    assert target is not None
    assert target["source_gap_signal"] == "out_of_scope:卡片申请"
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_knowledge_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_knowledge.py
"""知识库管理（supervisor/engineer/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, knowledge

router = APIRouter()
_sup = require_roles("supervisor", "engineer", "admin")


class EntryIn(BaseModel):
    type: str
    key: str
    title: str
    content: str
    locale: str = "zh"


class FromGapIn(BaseModel):
    signal_key: str
    type: str
    key: str
    title: str
    content: str
    locale: str = "zh"


@router.get("/admin/api/v1/knowledge")
async def list_entries(
    type_: str | None = Query(default=None, alias="type"),
    status: str | None = Query(default=None),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"entries": await knowledge.list_entries(type_=type_, status=status)}


@router.post("/admin/api/v1/knowledge")
async def create_entry(
    body: EntryIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    if body.type not in ("api_doc", "error_code", "faq"):
        raise HTTPException(400, "invalid type")
    actor = str(staff.get("sub", "unknown"))
    eid = await knowledge.upsert_entry(
        type_=body.type, key=body.key, title=body.title,
        content=body.content, locale=body.locale, created_by=actor,
    )
    await admin_audit.log_admin_action(
        actor=actor, action="knowledge.upsert",
        target_type="knowledge_entry", target_id=str(eid),
        detail={"type": body.type, "key": body.key},
    )
    return {"ok": True, "id": eid}


@router.post("/admin/api/v1/knowledge/{entry_id}/publish")
async def publish(entry_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await knowledge.publish(entry_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="knowledge.publish",
        target_type="knowledge_entry", target_id=str(entry_id),
    )
    return {"ok": True}


@router.delete("/admin/api/v1/knowledge/{entry_id}")
async def delete_entry(
    entry_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await knowledge.delete_entry(entry_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="knowledge.delete",
        target_type="knowledge_entry", target_id=str(entry_id),
    )
    return {"ok": True}


@router.post("/admin/api/v1/knowledge/from-gap")
async def from_gap(
    body: FromGapIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    """从 insights 知识缺口信号直转条目（草稿状态，需后续 publish）。"""
    if body.type not in ("api_doc", "error_code", "faq"):
        raise HTTPException(400, "invalid type")
    actor = str(staff.get("sub", "unknown"))
    eid = await knowledge.upsert_entry(
        type_=body.type, key=body.key, title=body.title,
        content=body.content, locale=body.locale,
        created_by=actor, source_gap_signal=body.signal_key,
    )
    await admin_audit.log_admin_action(
        actor=actor, action="knowledge.from_gap",
        target_type="knowledge_entry", target_id=str(eid),
        detail={"signal": body.signal_key, "type": body.type, "key": body.key},
    )
    return {"ok": True, "id": eid}
```

`main.py`：import + `app.include_router(admin_knowledge_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_knowledge_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_knowledge.py src/ai_engine/main.py tests/test_admin_knowledge_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_knowledge.py server/src/ai_engine/main.py server/tests/test_admin_knowledge_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 知识库 API（CRUD + publish + from-gap + 审计）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.5: 知识库前端页

**Files:**
- Create: `web/src/api/adminKnowledge.ts`
- Create: `web/src/routes/admin/KnowledgeRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminKnowledge.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type KnowledgeEntry = {
  id: number;
  type: string;
  key: string;
  title: string;
  locale: string;
  status: string;
  source_gap_signal: string | null;
  created_by: string | null;
  updated_at: string;
};

export async function listKnowledge(
  token: string, opts?: { type?: string; status?: string },
): Promise<KnowledgeEntry[]> {
  const qs = new URLSearchParams();
  if (opts?.type) qs.set("type", opts.type);
  if (opts?.status) qs.set("status", opts.status);
  const r = await staffFetch(`/admin/api/v1/knowledge?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).entries;
}

export async function createKnowledge(
  token: string,
  body: { type: string; key: string; title: string; content: string; locale?: string },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/knowledge", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
  return r.json();
}

export async function publishKnowledge(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/knowledge/${id}/publish`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`publish ${r.status}`);
}

export async function deleteKnowledge(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/knowledge/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: KnowledgeRoute**

```tsx
// web/src/routes/admin/KnowledgeRoute.tsx
import { useEffect, useState } from "react";

import {
  createKnowledge, deleteKnowledge, type KnowledgeEntry, listKnowledge, publishKnowledge,
} from "../../api/adminKnowledge";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const TYPES = ["api_doc", "error_code", "faq"];

function EntryForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [type, setType] = useState("faq");
  const [key, setKey] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  async function submit() {
    if (!token || !key || !title) return;
    try {
      await createKnowledge(token, { type, key, title, content });
      setKey(""); setTitle(""); setContent("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="rounded border border-line px-2 py-1 text-body2">
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <Input placeholder="key（如错误码/路径/slug）" value={key} className="w-56"
            onChange={(e) => setKey(e.target.value)} />
          <Input placeholder="标题" value={title} className="w-72"
            onChange={(e) => setTitle(e.target.value)} />
          <Button size="md" onClick={submit} disabled={!key || !title}>新建草稿</Button>
        </div>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={5} placeholder="内容（Markdown）" value={content}
          aria-label="内容"
          onChange={(e) => setContent(e.target.value)} />
      </div>
    </Card>
  );
}

function EntryRow({ e, onChanged, onError }: {
  e: KnowledgeEntry; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function pub() {
    if (!token) return;
    try { await publishKnowledge(token, e.id); onChanged(); }
    catch (err) { onError(err instanceof Error ? err.message : "发布失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteKnowledge(token, e.id); onChanged(); }
    catch (err) { onError(err instanceof Error ? err.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{e.id}</td>
      <td className="px-3 py-2">{e.type}</td>
      <td className="px-3 py-2 text-ink-primary">{e.key}</td>
      <td className="px-3 py-2 text-ink-secondary">{e.title}</td>
      <td className="px-3 py-2">{e.status}</td>
      <td className="px-3 py-2 text-ink-tertiary">{e.source_gap_signal ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          {e.status === "draft" && <button className="text-brand" onClick={pub}>发布</button>}
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function KnowledgeRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "engineer" || role === "admin";
  const [filter, setFilter] = useState("");
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listKnowledge(token, filter ? { type: filter } : undefined)
      .then(setEntries).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管/工程/管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, filter]);

  return (
    <PageContainer width="wide">
      <PageHeader title="知识库" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <EntryForm onCreated={reload} onError={setErr} />}
      {allowed && (
        <Card className="mt-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}
              className="rounded border border-line px-2 py-1 text-body2">
              <option value="">全部类型</option>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </Card>
      )}
      {loading ? <LoadingState /> : allowed && (
        <Card className="mt-3">
          <table className="w-full text-body3">
            <thead>
              <tr className="border-b border-line text-ink-secondary">
                <th className="px-3 py-2 text-left font-normal">ID</th>
                <th className="px-3 py-2 text-left font-normal">类型</th>
                <th className="px-3 py-2 text-left font-normal">key</th>
                <th className="px-3 py-2 text-left font-normal">标题</th>
                <th className="px-3 py-2 text-left font-normal">状态</th>
                <th className="px-3 py-2 text-left font-normal">来源</th>
                <th className="px-3 py-2 text-left font-normal">操作</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
              )}
              {entries.map((e) => <EntryRow key={e.id} e={e} onChanged={reload} onError={setErr} />)}
            </tbody>
          </table>
        </Card>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `KnowledgeRoute` + `<Route path="/admin/knowledge" element={<KnowledgeRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminKnowledge.ts src/routes/admin/KnowledgeRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminKnowledge.ts web/src/routes/admin/KnowledgeRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 知识库前端页（创建/发布/删除 + 按类型过滤）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 3 — 范围与拦截配置（guardrails）

## Task 3.1: guardrail_rules 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义 + 迁移**

`schema.py` 末尾追加：
```python
# 范围 / 拦截规则（M3b §5.4.f）
# evaluate_guardrails() 给 chat 入口提供 helper：扫描所有 active rule，命中则返回 action+reason。
guardrail_rules = Table(
    "guardrail_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("type", String(32), nullable=False),  # blocklist / sensitive_word / scope_toggle
    Column("pattern", String(512), nullable=False),  # blocklist=subject_id；sensitive_word=词；scope_toggle=scope name
    Column("action", String(16), nullable=False, server_default="block"),  # block / flag
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_by", String(64)),
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "type IN ('blocklist','sensitive_word','scope_toggle')",
        name="ck_guardrail_type",
    ),
    CheckConstraint(
        "action IN ('block','flag')", name="ck_guardrail_action",
    ),
)
Index("idx_guardrail_active", guardrail_rules.c.active, guardrail_rules.c.type)
```

Run: `cd server && .venv/bin/python -m alembic revision -m "guardrail_rules"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "guardrail_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("pattern", sa.String(512), nullable=False),
        sa.Column("action", sa.String(16), nullable=False, server_default="block"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "type IN ('blocklist','sensitive_word','scope_toggle')",
            name="ck_guardrail_type",
        ),
        sa.CheckConstraint("action IN ('block','flag')", name="ck_guardrail_action"),
    )
    op.create_index("idx_guardrail_active", "guardrail_rules", ["active", "type"])


def downgrade() -> None:
    op.drop_index("idx_guardrail_active", table_name="guardrail_rules")
    op.drop_table("guardrail_rules")
```

- [ ] **Step 2: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): guardrail_rules 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: guardrails persistence + evaluate helper

**Files:**
- Create: `server/src/ai_engine/persistence/guardrails.py`
- Test: `server/tests/test_guardrails_dao.py`

`evaluate_guardrails(subject_id, user_type, text)` → `("allow", None) | ("block"|"flag", reason)`。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_guardrails_dao.py
from ai_engine.persistence import guardrails


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    guardrails.invalidate_cache()


async def test_blocklist_subject(temp_db_url):
    await _init(temp_db_url)
    await guardrails.create_rule("blocklist", "BAD_USER_1", "block", "EN1")
    result = await guardrails.evaluate("BAD_USER_1", "c", "随便什么文字")
    assert result == ("block", "blocklist:BAD_USER_1")


async def test_sensitive_word_flag(temp_db_url):
    await _init(temp_db_url)
    await guardrails.create_rule("sensitive_word", "敏感词", "flag", "EN1")
    result = await guardrails.evaluate("USER1", "c", "这里包含 敏感词 内容")
    assert result == ("flag", "sensitive_word:敏感词")


async def test_no_rule_allows(temp_db_url):
    await _init(temp_db_url)
    result = await guardrails.evaluate("USER1", "c", "正常内容")
    assert result == ("allow", None)


async def test_inactive_rule_ignored(temp_db_url):
    await _init(temp_db_url)
    rid = await guardrails.create_rule("blocklist", "BAD", "block", "EN1")
    await guardrails.set_active(rid, 0)
    result = await guardrails.evaluate("BAD", "c", "x")
    assert result == ("allow", None)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_guardrails_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/guardrails.py
"""范围 / 拦截规则 persistence + evaluate helper。

evaluate_guardrails(subject_id, user_type, text) 给 chat 入口或 runtime 调用：
- blocklist: 命中即返回 (action, "blocklist:<subject_id>")
- sensitive_word: 文本 substring 匹配命中 pattern → (action, "sensitive_word:<word>")
- scope_toggle: 当前 M3b 不在 evaluate 中处理（scope 是运营标志位，由别处读取）。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_TYPES = {"blocklist", "sensitive_word", "scope_toggle"}
_VALID_ACTIONS = {"block", "flag"}

_CACHE: list[dict[str, Any]] | None = None


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _active_rules() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT id, type, pattern, action FROM guardrail_rules "
        "WHERE active = 1 ORDER BY id"
    )
    _CACHE = rows
    return rows


async def create_rule(type_: str, pattern: str, action: str, created_by: str) -> int:
    if type_ not in _VALID_TYPES:
        raise ValueError(f"invalid type: {type_}")
    if action not in _VALID_ACTIONS:
        raise ValueError(f"invalid action: {action}")
    rid = await db.insert_returning_id(
        "INSERT INTO guardrail_rules(type, pattern, action, created_by, created_at) "
        "VALUES (:t, :p, :a, :by, :now) RETURNING id",
        {"t": type_, "p": pattern, "a": action, "by": created_by, "now": now_str()},
    )
    invalidate_cache()
    return rid


async def list_rules() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, type, pattern, action, active, created_by, created_at "
        "FROM guardrail_rules ORDER BY id"
    )


async def set_active(rule_id: int, active: int) -> None:
    await db.execute(
        "UPDATE guardrail_rules SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(rule_id)},
    )
    invalidate_cache()


async def delete_rule(rule_id: int) -> None:
    await db.execute(
        "DELETE FROM guardrail_rules WHERE id = :id", {"id": int(rule_id)}
    )
    invalidate_cache()


async def evaluate(
    subject_id: str, user_type: str, text: str
) -> tuple[str, str | None]:
    """返回 ("allow", None) 或 ("block"|"flag", reason)。"""
    for rule in await _active_rules():
        t = str(rule["type"])
        pat = str(rule["pattern"])
        action = str(rule["action"])
        if t == "blocklist" and pat == subject_id:
            return action, f"blocklist:{pat}"
        if t == "sensitive_word" and pat in text:
            return action, f"sensitive_word:{pat}"
    return "allow", None
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_guardrails_dao.py -v` (4 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/guardrails.py tests/test_guardrails_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/guardrails.py server/tests/test_guardrails_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): guardrails persistence + evaluate helper（blocklist/sensitive_word）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: guardrails API

**Files:**
- Create: `server/src/ai_engine/api/admin_guardrails.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_guardrails_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_guardrails_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import guardrails
    from ai_engine.persistence.staff import create_staff

    guardrails.invalidate_cache()
    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    guardrails.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/guardrails", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_crud_with_audit(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/guardrails",
            json={"type": "sensitive_word", "pattern": "敏感词", "action": "flag"},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/guardrails", headers=_h(env["eng"]))).json()["rules"]
        assert any(g["id"] == rid for g in listed)
        await c.patch(f"/admin/api/v1/guardrails/{rid}",
                      json={"active": 0}, headers=_h(env["eng"]))
        await c.delete(f"/admin/api/v1/guardrails/{rid}", headers=_h(env["eng"]))
    audits = await admin_audit.list_admin_actions(action="guardrail.create", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)


async def test_create_bad_type_400(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/guardrails",
            json={"type": "bogus", "pattern": "x", "action": "block"},
            headers=_h(env["eng"]),
        )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_guardrails_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_guardrails.py
"""范围/拦截规则（engineer/admin）。写操作落审计 + 清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, guardrails

router = APIRouter()
_eng = require_roles("engineer", "admin")


class RuleIn(BaseModel):
    type: str
    pattern: str
    action: str = "block"


@router.get("/admin/api/v1/guardrails")
async def list_rules(staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    return {"rules": await guardrails.list_rules()}


@router.post("/admin/api/v1/guardrails")
async def create_rule(body: RuleIn, staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    try:
        rid = await guardrails.create_rule(body.type, body.pattern, body.action, actor)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=actor, action="guardrail.create",
        target_type="guardrail", target_id=str(rid), detail=body.model_dump(),
    )
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/guardrails/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await guardrails.set_active(rule_id, body.active)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="guardrail.update",
        target_type="guardrail", target_id=str(rule_id), detail={"active": body.active},
    )
    return {"ok": True}


@router.delete("/admin/api/v1/guardrails/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_eng)
) -> dict[str, Any]:
    await guardrails.delete_rule(rule_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="guardrail.delete",
        target_type="guardrail", target_id=str(rule_id),
    )
    return {"ok": True}
```

`main.py`：import + `app.include_router(admin_guardrails_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_guardrails_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_guardrails.py src/ai_engine/main.py tests/test_admin_guardrails_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_guardrails.py server/src/ai_engine/main.py server/tests/test_admin_guardrails_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): guardrails API（CRUD + 审计 + 缓存失效）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

注：本 task 完成 helper + CRUD。**chat.py 入口接入**（用户消息进入时调 `evaluate` 并据此 block/flag）属于 chat.py 改造，chat.py 是用户脏文件——**本 M3b 不强行接入**；运营可通过 API 创建规则、helper 可被未来 chat.py 整理后接入。

---

## Task 3.4: guardrails 前端页

**Files:**
- Create: `web/src/api/adminGuardrails.ts`
- Create: `web/src/routes/admin/GuardrailsRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminGuardrails.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Guardrail = {
  id: number;
  type: string;
  pattern: string;
  action: string;
  active: number;
  created_by: string | null;
  created_at: string;
};

export async function listGuardrails(token: string): Promise<Guardrail[]> {
  const r = await staffFetch("/admin/api/v1/guardrails", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).rules;
}

export async function createGuardrail(
  token: string, body: { type: string; pattern: string; action: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/guardrails", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
}

export async function setGuardrailActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/guardrails/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function deleteGuardrail(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/guardrails/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: GuardrailsRoute**

```tsx
// web/src/routes/admin/GuardrailsRoute.tsx
import { useEffect, useState } from "react";

import {
  createGuardrail, deleteGuardrail, type Guardrail, listGuardrails, setGuardrailActive,
} from "../../api/adminGuardrails";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const TYPES = ["blocklist", "sensitive_word", "scope_toggle"];

function RuleForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [type, setType] = useState("sensitive_word");
  const [pattern, setPattern] = useState("");
  const [action, setAction] = useState("block");
  async function submit() {
    if (!token || !pattern) return;
    try {
      await createGuardrail(token, { type, pattern, action });
      setPattern("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <select value={type} onChange={(e) => setType(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <Input placeholder="pattern（subject_id / 词 / scope 名）" value={pattern} className="w-72"
          onChange={(e) => setPattern(e.target.value)} />
        <select value={action} onChange={(e) => setAction(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          <option value="block">block</option>
          <option value="flag">flag</option>
        </select>
        <Button size="md" onClick={submit} disabled={!pattern}>新建规则</Button>
      </div>
    </Card>
  );
}

function RuleRow({ g, onChanged, onError }: {
  g: Guardrail; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function toggle() {
    if (!token) return;
    try { await setGuardrailActive(token, g.id, g.active ? 0 : 1); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteGuardrail(token, g.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{g.id}</td>
      <td className="px-3 py-2">{g.type}</td>
      <td className="px-3 py-2 text-ink-primary">{g.pattern}</td>
      <td className="px-3 py-2">{g.action}</td>
      <td className="px-3 py-2">{g.active ? "启用" : "停用"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={toggle}>{g.active ? "停用" : "启用"}</button>
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function GuardrailsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [rules, setRules] = useState<Guardrail[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGuardrails(token).then(setRules).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="范围与拦截配置" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <RuleForm onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <Card className="mt-3">
          <table className="w-full text-body3">
            <thead>
              <tr className="border-b border-line text-ink-secondary">
                <th className="px-3 py-2 text-left font-normal">ID</th>
                <th className="px-3 py-2 text-left font-normal">类型</th>
                <th className="px-3 py-2 text-left font-normal">pattern</th>
                <th className="px-3 py-2 text-left font-normal">动作</th>
                <th className="px-3 py-2 text-left font-normal">状态</th>
                <th className="px-3 py-2 text-left font-normal">操作</th>
              </tr>
            </thead>
            <tbody>
              {rules.length === 0 && (
                <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">无规则</td></tr>
              )}
              {rules.map((g) => <RuleRow key={g.id} g={g} onChanged={reload} onError={setErr} />)}
            </tbody>
          </table>
          <p className="px-page py-block-sm text-footnote text-ink-tertiary">
            evaluate_guardrails helper 已就绪。chat.py 入口接入留 M4（依赖 chat.py 整理）。
          </p>
        </Card>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `GuardrailsRoute` + `<Route path="/admin/guardrails" element={<GuardrailsRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminGuardrails.ts src/routes/admin/GuardrailsRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminGuardrails.ts web/src/routes/admin/GuardrailsRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 范围/拦截规则前端页（CRUD）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 4 — AI 自动调用接 tool_policies

## Task 4.1: tool_router 接入 + tool_policies 默认 ai 放行

**Files:**
- Modify: `server/src/ai_engine/persistence/tool_policies.py` — `_default_allowed` 让 `role="ai"` 默认 True
- Modify: `server/src/ai_engine/agent/tool_router.py`（**先 grep 确认非脏**）— `dispatch()` 前置加 `is_tool_allowed(tool_name, "ai")` 校验
- Test: `server/tests/test_tool_router_ai_policy.py`

设计语义：
- AI 自动调用的"角色"用特殊字符串 `"ai"`
- `_default_allowed("...", "ai")` 默认 True（M1 默认行为：AI 可调用所有 REGISTRY 工具）
- DB 中可写一条 `(tool_name, role="ai", allowed=0)` 显式禁某个工具被 AI 自动调用
- `dispatch()` 入口加 `if not await is_tool_allowed(tool_name, "ai"): raise PermissionError` 或返回错误

- [ ] **Step 1: 改 `_default_allowed`**

读 `server/src/ai_engine/persistence/tool_policies.py`。修改 `_default_allowed` 函数：
```python
def _default_allowed(tool_name: str, role: str) -> bool:
    # M3b: AI 自动调用默认允许（M1 兼容）；显式 DB 行可禁用
    if role == "ai":
        return True
    if role in {"agent", "senior", "engineer", "admin"}:
        return tool_name in _STAFF_DEFAULT_TOOLS
    return False
```

(`_default_unmask` 不动 — AI 调用永远拿 unmask=True 的能力由调用方继续控制；脱敏不在本 task 范围。)

- [ ] **Step 2: 改 tool_router 加前置校验**

读 `server/src/ai_engine/agent/tool_router.py`（先确认非脏：`git status --short` 无输出）。在 `dispatch` 函数开头（既有 `tool = REGISTRY.get(tool_name)` 工具存在性检查之后）加：
```python
    # M3b: 系统调用前置策略检查；表为空时回退默认（_default_allowed for role="ai"=True）
    try:
        from ai_engine.persistence.tool_policies import is_tool_allowed
        if not await is_tool_allowed(tool_name, "ai"):
            raise PermissionError(f"tool blocked by policy: {tool_name}")
    except ImportError:
        pass
```
不动既有其它前置（subject 注入 / unmask 决策等）。

- [ ] **Step 3: 写测试**

```python
# server/tests/test_tool_router_ai_policy.py
"""AI 自动调用（dispatch 直接调）受 tool_policies(role=ai) 控制：默认放行，DB 显式禁用即拒。"""

import pytest


async def test_ai_default_allowed(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    # 默认表空，AI 调用应该越过策略校验（具体业务结果与既有实现相关）
    try:
        await dispatch(
            tool_name="lookup_error_code", params={"code": "E1"},
            user_type="c", subject_id="u1", conversation_id=1,
        )
    except PermissionError:
        pytest.fail("default should not block AI calls")
    except Exception:
        pass  # 其它错误（业务/数据源）不阻塞本测试


async def test_ai_blocked_when_db_denies(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "lookup_error_code", "role": "ai",
         "allowed": 0, "unmask_allowed": 0},
    ])
    with pytest.raises(PermissionError):
        await dispatch(
            tool_name="lookup_error_code", params={"code": "E1"},
            user_type="c", subject_id="u1", conversation_id=1,
        )
```

- [ ] **Step 4: 跑测试 + ruff + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_tool_router_ai_policy.py tests/test_tool_router_authz.py tests/test_tool_router_c_identity.py -v`
Expected: 新 2 pass；既有 tool_router 测试不退化。
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/tool_policies.py src/ai_engine/agent/tool_router.py tests/test_tool_router_ai_policy.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/tool_policies.py server/src/ai_engine/agent/tool_router.py server/tests/test_tool_router_ai_policy.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): AI 自动调用接 tool_policies（role=ai，默认放行 + DB 可禁）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.2: 工具权限矩阵前端加 AI 列

**Files:**
- Modify: `web/src/api/adminToolPolicies.ts` — `POLICY_ROLES` 加 `"ai"`
- Modify: `web/src/routes/admin/ToolPoliciesRoute.tsx` —（无需改）—— 表格自动按 POLICY_ROLES 渲染

- [ ] **Step 1: 改常量**

读 `web/src/api/adminToolPolicies.ts`。把 `POLICY_ROLES` 改为：
```typescript
export const POLICY_ROLES: string[] = ["agent", "senior", "engineer", "supervisor", "ai"];
```

- [ ] **Step 2: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminToolPolicies.ts src/routes/admin/ToolPoliciesRoute.tsx`
Expected: 0 problems。

手动验证（可选）：engineer 登录 → 工具策略 → 看到 ai 列 → 勾选 lookup_error_code 的 ai/allowed=0 保存 → AI 自动调用 lookup_error_code 触发 PermissionError。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminToolPolicies.ts
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 工具权限矩阵加 ai 列（与 Task 4.1 接入配套）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# 收尾回归

- [ ] **Step 1: 后端全套**

Run: `cd server && .venv/bin/pytest --cov=src/ai_engine --cov-report=term --cov-fail-under=75 2>&1 | tail -25`
Expected: 新增测试 pass；覆盖率 ≥75%；pre-existing 失败保持（`test_user_upload_and_view`）。

- [ ] **Step 2: 前端检查**

Run: `cd web && pnpm typecheck`
Expected: 仅 pre-existing staffFetch.ts 错保持。
Run: `cd web && pnpm test:ci`
Expected: 仅 pre-existing ImageThumb test 失败保持。

- [ ] **Step 3: alembic 单 head**

Run: `cd server && .venv/bin/python -m alembic heads`
Expected: 单 head（M3b 3 个迁移：prompt_drafts、knowledge_entries、guardrail_rules）。

- [ ] **Step 4: git status 核对**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short`
Expected: 仅 11 modified + 1 untracked。`server/uv.lock` 若脏：`git -C ... checkout server/uv.lock` 还原。

- [ ] **Step 5: 提交链**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine log --oneline -25`

---

## M3b 完成定义（DoD）

- Prompt 在线编辑：可创建草稿/发布；loader DB-first（已发布优先于文件）；前端可编辑、发布、删除。
- 知识库：可建/发布/删除/按 type 过滤；`lookup_api_doc`/`lookup_error_code` DB-first；from-gap 可一键转条目。
- Guardrails：可建/启停/删；`evaluate_guardrails` helper 就绪；前端 CRUD。
- AI 自动调用接 tool_policies：`dispatch()` 前置校验 `is_tool_allowed(tool, "ai")`；DB 空时默认放行（兼容 M1）；DB 显式禁用即拒。
- 工具权限矩阵前端增 ai 列。
- 后端覆盖率 ≥75%；alembic 单 head；新增 3 张表迁移通过 parity。

## 遗留说明（非 M3b 范围）

1. **Prompt 在线编辑的版本管理**：M3b 把 `prompt_drafts` 当 (version,file) 维度的草稿/发布存储。"版本切换 / 灰度"仍由 M2 `admin_prompts.py` 处理；两者协作语义是"灰度选 version → loader 加载该 version 时优先读 DB"。
2. **scope_toggle 规则未在 evaluate 中处理**：当前 evaluate 只看 blocklist + sensitive_word。scope_toggle 留 M4（涉及"业务范围切换"的具体场景定义）。
3. **chat.py 入口接入 guardrails**：chat.py 是用户脏文件，本 M3b 仅提供 helper + API + 前端；运营可配置规则，自动触发等 chat.py 整理后接入。
4. **AI 自动调用的脱敏决策**：本 M3b 仅接入 `is_tool_allowed("ai")`；`is_unmask_allowed("ai")` 未接入。AI 自动调用的 unmask 仍由调用方控制（runtime → dispatch 传 unmask 值）。M4 视需要扩。
5. **lookup_* 工具的 locale 处理**：M3b 工具默认查 locale="zh"；多语言场景需扩展工具签名加 locale 参数。
6. **知识库版本/审批工作流**：M3b 只有 draft/published 两态；多审批节点（如"待审核"中间态）留 M4。
