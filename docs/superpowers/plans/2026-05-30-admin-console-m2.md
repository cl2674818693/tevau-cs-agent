# 管理后台 M2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1 管理后台基础上落地 M2（P1）：会话质检、客服满意度（采集+展示）、客服绩效详情、AI 工具权限矩阵、Token 成本大盘、RBAC 基础矩阵。

**Architecture:** 沿用 M1 的分层与模式——SQLAlchemy Core schema + 每域 persistence + FastAPI APIRouter（`Depends(require_roles)`）+ React Route。新增表都配独立 alembic 迁移（parity 测试强制）。本里程碑额外两块改既有代码：工具权限矩阵接入既有的 `_STAFF_TOOL_WHITELIST`/`unmask` 逻辑；token 成本写入路径加 `model` 维度。后端严格 TDD，前端给完整组件 + 针对性 lint。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async, sqlite+aiosqlite 测试 / postgresql+asyncpg 生产) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind / vitest。

---

## 关键约定（所有 Task 必须遵守，照搬 M1）

1. **可选筛选 SQL** 一律 `(CAST(:p AS TEXT) IS NULL OR col = :p)`。
2. **时间列** 用 `from ai_engine.persistence.schema import now_str`。
3. **新增表** 必须：① 加进 `schema.py` 的 `metadata`；② 加一个**独立** alembic 迁移（绝不修改既有迁移文件）。每个加表 task 用 `alembic revision -m "..."` 生成骨架。
4. **后端测试** 用 `temp_db_url`/`seeded_db` fixture + `ASGITransport(app=main_mod.app)` + `AsyncClient`，参照 `tests/test_admin_staff_api.py`。
5. **角色 gate**：用 M1 已有 `require_roles(*roles)` 依赖（`server/src/ai_engine/auth/staff_session.py`）。
6. **写操作审计**：所有后台写操作调用 `admin_audit.log_admin_action(...)`（M1 已实现）。
7. **覆盖率门槛** `--cov-fail-under=75`；跑单测 `cd server && python -m pytest tests/xxx.py -v`；全套 `cd server && make test`。
8. **git discipline**：在 `main` 工作（用户同意）。工作树有 12 个**预存脏文件**（M1 时已记录的），**绝不**用 `git add -A`/`git add .`；用 `git add <精确路径>` 仅暂存本 task 文件。如果出现 `server/uv.lock` 脏，那是测试副产物——本 task 不要 stage 它；controller 会定期还原。
9. **PageContainer width** 只接受 `"wide" | "default" | "form" | "narrow"`。
10. **前端 lint**：项目全局 `pnpm lint` 因 PRE-EXISTING warnings 失败——用 `pnpm typecheck` + `npx eslint <你的具体文件>`，每个自己改/建的文件必须 0 problems。eslint `max-lines-per-function` ≤80，超了拆子组件。
11. **commit message** 中文 + 末尾必须的 Co-Authored-By 行（见模板）。

---

## M1 已交付基线（M2 直接复用）

- 角色：`agent / senior / engineer / admin / supervisor / manager`（CheckConstraint 已扩展）。
- 鉴权依赖：`require_roles(*roles)`。
- 审计表与 helper：`admin_audit_log` 表 + `persistence/admin_audit.py` 的 `log_admin_action / list_admin_actions`。
- 后台外壳：`web/src/components/StaffLayout.tsx` 的 `NAV_ITEMS` 已用 `roles?: string[]` 结构（M2 直接加项即可）。
- M1 已存在的后台页：`/admin/dashboard`、`/admin/staff`、`/admin/sla`、`/admin/audit`、`/admin/prompts`。
- 前端 UI 组件：`web/src/components/ui/*`（Alert/Button/Card/Input/PageContainer+PageHeader/LoadingState）。
- 前端 API 客户端模式：`web/src/api/admin*.ts`（`staffFetch` + `authHeaders`）。

---

## 文件结构总览

**后端新增**：
- `server/src/ai_engine/persistence/admin_qa.py` — 质检评分卡 CRUD + 提交/列表
- `server/src/ai_engine/persistence/agent_ratings.py` — 满意度写入 + 聚合
- `server/src/ai_engine/persistence/staff_performance.py` — 客服绩效详情聚合（接管/解决时长/满意度/质检均分）
- `server/src/ai_engine/persistence/tool_policies.py` — 工具权限读 + 内存缓存 + 默认回退
- `server/src/ai_engine/persistence/admin_cost.py` — 成本聚合 + 单价换算
- `server/src/ai_engine/api/admin_qa.py` — 质检 API
- `server/src/ai_engine/api/agent_ratings.py` — 满意度采集（C/B 端）+ 后台聚合
- `server/src/ai_engine/api/admin_staff_performance.py` — 客服绩效详情 API
- `server/src/ai_engine/api/admin_tool_policies.py` — 工具权限矩阵 API
- `server/src/ai_engine/api/admin_cost.py` — 成本大盘 API
- 5 个独立 alembic 迁移（每加表/改列一个）

**后端修改**（**这些文件需 grep 确认非脏后再改**）：
- `server/src/ai_engine/persistence/schema.py` — 新增 5 张表 + `daily_token_usage` 加 `model` 列
- `server/src/ai_engine/main.py` — include 5 个新 router
- `server/src/ai_engine/api/staff_conversations.py` — `_STAFF_TOOL_WHITELIST` 改为读 DB（`tool_policies`），保留代码默认作 fallback
- `server/src/ai_engine/agent/tool_router.py` — `dispatch()` 的 unmask 决策从"硬编码 role==engineer"改为读 `tool_policies`
- `server/src/ai_engine/governance/token_budget.py` — `_record` / `check_and_record` 新增 `model` 参数
- `server/src/ai_engine/agent/runtime.py` — `_budget_gate` 调用处把 `model` 传进 `check_and_record`

**前端新增**：
- `web/src/api/adminQa.ts`、`adminAgentRatings.ts`、`adminStaffPerformance.ts`、`adminToolPolicies.ts`、`adminCost.ts`
- `web/src/api/userAgentRating.ts` — C 端满意度采集 client
- `web/src/components/AgentRatingButton.tsx` — C 端评分按钮 + 弹窗
- `web/src/routes/admin/QaReviewRoute.tsx`、`StaffPerformanceRoute.tsx`、`ToolPoliciesRoute.tsx`、`CostRoute.tsx`、`RbacRoute.tsx`

**前端修改**：
- `web/src/components/StaffLayout.tsx` — 加 5 个 M2 菜单项
- `web/src/App.tsx` — 注册 5 个新路由
- `web/src/routes/ChatRoute.tsx` — 挂 `<AgentRatingButton />`（**必须确认本文件非脏才改，脏了则改 ChatWindow.tsx**）
- `web/src/routes/admin/StaffAccountsRoute.tsx` — 每行加"查看绩效"跳转链接

---

# Phase 0 — 菜单扩展（前置）

## Task 0.1: 后台菜单加 M2 5 项

**Files:**
- Modify: `web/src/components/StaffLayout.tsx`

- [ ] **Step 1: 改 NAV_ITEMS**

在 `web/src/components/StaffLayout.tsx`：
- 把 lucide-react import 增加：`ClipboardCheck`、`UserCog`、`KeySquare`、`Wallet`、`Shield`。
- 在 `NAV_ITEMS` 末尾追加 5 项（保留 M1 已有项不动）：
```typescript
  { to: "/admin/qa", label: "会话质检", short: "质检", icon: ClipboardCheck, roles: ["supervisor", "admin"] },
  { to: "/admin/performance", label: "客服绩效", short: "绩效", icon: UserCog, roles: ["supervisor", "admin"] },
  { to: "/admin/tools", label: "工具策略", short: "工具", icon: KeySquare, roles: ["engineer", "admin"] },
  { to: "/admin/cost", label: "成本大盘", short: "成本", icon: Wallet, roles: ["engineer", "manager", "admin"] },
  { to: "/admin/rbac", label: "角色权限", short: "RBAC", icon: Shield, roles: ["admin"] },
```

- [ ] **Step 2: typecheck + 针对性 lint**

Run: `cd web && pnpm typecheck && npx eslint src/components/StaffLayout.tsx`
Expected: typecheck pass；eslint StaffLayout.tsx 0 problems。

- [ ] **Step 3: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine
git add web/src/components/StaffLayout.tsx
git commit -m "feat(admin): 后台菜单加 M2 五项占位（质检/绩效/工具/成本/RBAC）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
Before committing, `git status` — 确认仅 StaffLayout.tsx 被 stage。

---

# Phase 1 — 会话质检

## Task 1.1: qa_scorecards + qa_reviews 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移文件

- [ ] **Step 1: 加表到 schema.py**

在 `server/src/ai_engine/persistence/schema.py` 末尾追加：
```python
# 质检评分卡模板（运营定义评分项 JSON）
qa_scorecards = Table(
    "qa_scorecards",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("items_json", Text, nullable=False),  # [{"key":"polite","label":"礼貌用语","weight":1}, ...]
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
)

# 质检记录：reviewer 对一通会话按 scorecard 打分
qa_reviews = Table(
    "qa_reviews",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("reviewer_staff_id", String(64), nullable=False),
    Column("scorecard_id", Integer, nullable=False),
    Column("score", Integer, nullable=False),  # 0-100
    Column("items_result_json", Text, nullable=False),  # {"polite":1,"accurate":0,...}
    Column("tags", String(256)),  # 逗号分隔标签：violation,excellent,needs_improvement
    Column("comment", Text),
    Column("created_at", String(32), nullable=False),
)
Index("idx_qa_reviews_conv", qa_reviews.c.conversation_id)
Index("idx_qa_reviews_reviewer", qa_reviews.c.reviewer_staff_id, qa_reviews.c.created_at)
```

- [ ] **Step 2: 确认 parity 测试 FAIL**

Run: `cd server && python -m pytest tests/test_alembic_migrations.py::test_alembic_upgrade_matches_init_db_schema -v`
Expected: FAIL — `alembic 缺表: {'qa_scorecards', 'qa_reviews'}`。

- [ ] **Step 3: 建独立迁移**

Run: `cd server && alembic revision -m "qa_scorecards_reviews"`
编辑生成的文件，填 upgrade/downgrade：
```python
def upgrade() -> None:
    op.create_table(
        "qa_scorecards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_table(
        "qa_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_staff_id", sa.String(64), nullable=False),
        sa.Column("scorecard_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("items_result_json", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(256), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_qa_reviews_conv", "qa_reviews", ["conversation_id"])
    op.create_index(
        "idx_qa_reviews_reviewer", "qa_reviews",
        ["reviewer_staff_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_qa_reviews_reviewer", table_name="qa_reviews")
    op.drop_index("idx_qa_reviews_conv", table_name="qa_reviews")
    op.drop_table("qa_reviews")
    op.drop_table("qa_scorecards")
```
保留 alembic 自动生成的 revision/down_revision 头。`from alembic import op` 和 `import sqlalchemy as sa` 都用得到，保留。

- [ ] **Step 4: parity 测试 PASS**

Run: `cd server && python -m pytest tests/test_alembic_migrations.py -v`
Expected: 2 passed。Run: `cd server && python -m alembic heads` — 单 head 指向你的新 revision。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git commit -m "feat(admin): qa_scorecards + qa_reviews 表 + 迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
提交前 `git status` 确认仅 schema.py + 你的新迁移在 stage（不带其它）。

---

## Task 1.2: 质检 persistence

**Files:**
- Create: `server/src/ai_engine/persistence/admin_qa.py`
- Test: `server/tests/test_admin_qa_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_qa_dao.py
import json

from ai_engine.persistence import admin_qa


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_scorecard_crud(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard("默认评分卡", [{"key": "polite", "label": "礼貌", "weight": 1}])
    rows = await admin_qa.list_scorecards()
    assert len(rows) == 1 and rows[0]["id"] == sid
    parsed = json.loads(rows[0]["items_json"])
    assert parsed[0]["key"] == "polite"
    await admin_qa.set_scorecard_active(sid, 0)
    assert int((await admin_qa.list_scorecards())[0]["active"]) == 0


async def test_review_submit_and_list_by_conv(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard("c1", [{"key": "polite"}])
    rid = await admin_qa.submit_review(
        conversation_id=42, reviewer_staff_id="SUP1", scorecard_id=sid,
        score=88, items_result={"polite": 1}, tags="excellent", comment="不错",
    )
    rows = await admin_qa.list_reviews(conversation_id=42)
    assert len(rows) == 1 and rows[0]["id"] == rid
    assert rows[0]["score"] == 88
    assert rows[0]["tags"] == "excellent"


async def test_list_reviews_filter_by_reviewer(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_qa.create_scorecard("c1", [])
    await admin_qa.submit_review(conversation_id=1, reviewer_staff_id="SUP1",
                                 scorecard_id=sid, score=80, items_result={})
    await admin_qa.submit_review(conversation_id=2, reviewer_staff_id="SUP2",
                                 scorecard_id=sid, score=60, items_result={})
    rows = await admin_qa.list_reviews(reviewer_staff_id="SUP1")
    assert len(rows) == 1 and rows[0]["reviewer_staff_id"] == "SUP1"
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd server && python -m pytest tests/test_admin_qa_dao.py -v`
Expected: ModuleNotFoundError admin_qa。

- [ ] **Step 3: 实现 persistence**

```python
# server/src/ai_engine/persistence/admin_qa.py
"""会话质检：评分卡 CRUD + 质检提交/列表。"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_scorecard(name: str, items: list[dict[str, Any]]) -> int:
    return await db.insert_returning_id(
        "INSERT INTO qa_scorecards(name, items_json, created_at) "
        "VALUES (:n, :items, :now) RETURNING id",
        {"n": name, "items": json.dumps(items, ensure_ascii=False), "now": now_str()},
    )


async def list_scorecards(active_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, name, items_json, active, created_at FROM qa_scorecards"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    return await db.fetch_all(sql)


async def set_scorecard_active(scorecard_id: int, active: int) -> None:
    await db.execute(
        "UPDATE qa_scorecards SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(scorecard_id)},
    )


async def submit_review(
    conversation_id: int,
    reviewer_staff_id: str,
    scorecard_id: int,
    score: int,
    items_result: dict[str, Any],
    tags: str | None = None,
    comment: str | None = None,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO qa_reviews(conversation_id, reviewer_staff_id, scorecard_id, score, "
        "items_result_json, tags, comment, created_at) "
        "VALUES (:cid, :sid, :sc, :score, :items, :tags, :cmt, :now) RETURNING id",
        {
            "cid": int(conversation_id),
            "sid": reviewer_staff_id,
            "sc": int(scorecard_id),
            "score": int(score),
            "items": json.dumps(items_result, ensure_ascii=False),
            "tags": tags,
            "cmt": comment,
            "now": now_str(),
        },
    )


async def list_reviews(
    conversation_id: int | None = None,
    reviewer_staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, conversation_id, reviewer_staff_id, scorecard_id, score, "
        "items_result_json, tags, comment, created_at FROM qa_reviews "
        "WHERE (CAST(:cid AS TEXT) IS NULL OR conversation_id = :cid) "
        "AND (CAST(:rsid AS TEXT) IS NULL OR reviewer_staff_id = :rsid) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {
            "cid": conversation_id, "rsid": reviewer_staff_id,
            "df": date_from, "dt": date_to,
            "lim": limit, "off": offset,
        },
    )


async def avg_score_by_reviewer(
    reviewer_staff_id: str, date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    """绩效详情用：单客服质检均分 + 计数。"""
    row = await db.fetch_one(
        "SELECT COUNT(*) AS n, AVG(score) AS avg_score FROM qa_reviews "
        "WHERE reviewer_staff_id = :rsid "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt)",
        {"rsid": reviewer_staff_id, "df": date_from, "dt": date_to},
    )
    return {
        "count": int(row["n"]) if row and row["n"] is not None else 0,
        "avg_score": float(row["avg_score"]) if row and row["avg_score"] is not None else 0.0,
    }
```

- [ ] **Step 4: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_qa_dao.py -v` (3 pass)
Run: `cd server && ruff check src/ai_engine/persistence/admin_qa.py tests/test_admin_qa_dao.py` clean。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/admin_qa.py server/tests/test_admin_qa_dao.py
git commit -m "feat(admin): 质检 persistence（评分卡 CRUD + 提交/列表 + 均分聚合）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: 质检 API + 注册 + 审计

**Files:**
- Create: `server/src/ai_engine/api/admin_qa.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_qa_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_qa_api.py
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
    yield {"sup": issue_staff_token("SUP1", "supervisor"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        assert (await c.get("/admin/api/v1/qa/scorecards", headers=_h(env["agent"]))).status_code == 403


async def test_scorecard_create_and_list(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/qa/scorecards",
            json={"name": "默认", "items": [{"key": "polite", "label": "礼貌", "weight": 1}]},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/qa/scorecards", headers=_h(env["sup"]))).json()["scorecards"]
    assert any(s["name"] == "默认" for s in listed)


async def test_submit_review_writes_audit(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        sid_resp = await c.post(
            "/admin/api/v1/qa/scorecards",
            json={"name": "c1", "items": [{"key": "polite"}]},
            headers=_h(env["sup"]),
        )
        sid = sid_resp.json()["id"]
        r = await c.post(
            "/admin/api/v1/qa/reviews",
            json={"conversation_id": 7, "scorecard_id": sid, "score": 88,
                  "items_result": {"polite": 1}, "tags": "excellent", "comment": "好"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/qa/reviews?conversation_id=7",
                              headers=_h(env["sup"]))).json()["reviews"]
    assert len(listed) == 1 and listed[0]["score"] == 88
    audits = await admin_audit.list_admin_actions(action="qa.review.submit", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd server && python -m pytest tests/test_admin_qa_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_qa.py
"""会话质检（supervisor/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_qa

router = APIRouter()
_sup = require_roles("supervisor", "admin")


# ── 评分卡 ────────────────────────────────────────────────────────────────

@router.get("/admin/api/v1/qa/scorecards")
async def list_scorecards(
    active_only: bool = Query(default=False),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"scorecards": await admin_qa.list_scorecards(active_only=active_only)}


class ScorecardIn(BaseModel):
    name: str
    items: list[dict[str, Any]]


@router.post("/admin/api/v1/qa/scorecards")
async def create_scorecard(body: ScorecardIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    sid = await admin_qa.create_scorecard(body.name, body.items)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="qa.scorecard.create",
        target_type="qa_scorecard", target_id=str(sid), detail={"name": body.name},
    )
    return {"ok": True, "id": sid}


class ScorecardPatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/qa/scorecards/{scorecard_id}")
async def patch_scorecard(
    scorecard_id: int, body: ScorecardPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await admin_qa.set_scorecard_active(scorecard_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="qa.scorecard.update",
        target_type="qa_scorecard", target_id=str(scorecard_id), detail={"active": body.active},
    )
    return {"ok": True}


# ── 质检记录 ──────────────────────────────────────────────────────────────

class ReviewIn(BaseModel):
    conversation_id: int
    scorecard_id: int
    score: int
    items_result: dict[str, Any]
    tags: str | None = None
    comment: str | None = None


@router.post("/admin/api/v1/qa/reviews")
async def submit_review(body: ReviewIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    rid = await admin_qa.submit_review(
        conversation_id=body.conversation_id,
        reviewer_staff_id=staff.get("sub", "unknown"),
        scorecard_id=body.scorecard_id,
        score=body.score,
        items_result=body.items_result,
        tags=body.tags,
        comment=body.comment,
    )
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="qa.review.submit",
        target_type="qa_review", target_id=str(rid),
        detail={"conversation_id": body.conversation_id, "score": body.score},
    )
    return {"ok": True, "id": rid}


@router.get("/admin/api/v1/qa/reviews")
async def list_reviews(
    conversation_id: int | None = Query(default=None),
    reviewer_staff_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"reviews": await admin_qa.list_reviews(
        conversation_id=conversation_id,
        reviewer_staff_id=reviewer_staff_id,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_qa import router as admin_qa_router`，并加 `app.include_router(admin_qa_router)` 紧跟其它 admin router。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_qa_api.py -v` (3 pass)
Run: `cd server && ruff check src/ai_engine/api/admin_qa.py src/ai_engine/main.py tests/test_admin_qa_api.py` clean。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_qa.py server/src/ai_engine/main.py server/tests/test_admin_qa_api.py
git commit -m "feat(admin): 质检 API（评分卡/提交记录，supervisor 鉴权+审计）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.4: 质检前端页

**Files:**
- Create: `web/src/api/adminQa.ts`
- Create: `web/src/routes/admin/QaReviewRoute.tsx`
- Modify: `web/src/App.tsx` (注册路由)

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminQa.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ScorecardItem = { key: string; label?: string; weight?: number };

export type Scorecard = {
  id: number;
  name: string;
  items_json: string;
  active: number;
  created_at: string;
};

export type QaReview = {
  id: number;
  conversation_id: number;
  reviewer_staff_id: string;
  scorecard_id: number;
  score: number;
  items_result_json: string;
  tags: string | null;
  comment: string | null;
  created_at: string;
};

export async function listScorecards(token: string, activeOnly = false): Promise<Scorecard[]> {
  const r = await staffFetch(`/admin/api/v1/qa/scorecards?active_only=${activeOnly}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).scorecards;
}

export async function createScorecard(
  token: string, body: { name: string; items: ScorecardItem[] },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/qa/scorecards", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create failed ${r.status}`);
}

export async function submitReview(
  token: string,
  body: {
    conversation_id: number;
    scorecard_id: number;
    score: number;
    items_result: Record<string, number>;
    tags?: string;
    comment?: string;
  },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/qa/reviews", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`submit failed ${r.status}`);
}

export async function listReviews(
  token: string,
  opts?: { conversation_id?: number; reviewer_staff_id?: string },
): Promise<QaReview[]> {
  const qs = new URLSearchParams();
  if (opts?.conversation_id != null) qs.set("conversation_id", String(opts.conversation_id));
  if (opts?.reviewer_staff_id) qs.set("reviewer_staff_id", opts.reviewer_staff_id);
  const r = await staffFetch(`/admin/api/v1/qa/reviews?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`reviews failed ${r.status}`);
  return (await r.json()).reviews;
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/QaReviewRoute.tsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createScorecard, listReviews, listScorecards, submitReview,
  type QaReview, type Scorecard, type ScorecardItem,
} from "../../api/adminQa";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function ScorecardCreator({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [raw, setRaw] = useState('[{"key":"polite","label":"礼貌用语"}]');
  async function submit() {
    if (!token || !name) return;
    let items: ScorecardItem[];
    try { items = JSON.parse(raw); }
    catch { onError("评分项 JSON 格式错"); return; }
    try { await createScorecard(token, { name, items }); setName(""); onCreated(); }
    catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <Input placeholder="评分卡名称" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={3} value={raw} onChange={(e) => setRaw(e.target.value)}
          aria-label="评分项 JSON" />
        <div><Button size="md" onClick={submit} disabled={!name}>新建评分卡</Button></div>
      </div>
    </Card>
  );
}

function ReviewForm({ scorecards, defaultConvId, onSubmitted, onError }: {
  scorecards: Scorecard[]; defaultConvId: number;
  onSubmitted: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [convId, setConvId] = useState(defaultConvId);
  const [scid, setScid] = useState(scorecards[0]?.id ?? 0);
  const [score, setScore] = useState(80);
  const [tags, setTags] = useState("");
  const [comment, setComment] = useState("");
  async function submit() {
    if (!token || !scid) return;
    try {
      await submitReview(token, {
        conversation_id: convId, scorecard_id: scid, score,
        items_result: {}, tags: tags || undefined, comment: comment || undefined,
      });
      onSubmitted();
    } catch (e) { onError(e instanceof Error ? e.message : "提交失败"); }
  }
  return (
    <Card className="mt-3">
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input type="number" min={1} value={convId} aria-label="会话 ID"
          onChange={(e) => setConvId(Number(e.target.value))} className="w-28" />
        <select value={scid} onChange={(e) => setScid(Number(e.target.value))}
          className="rounded border border-line px-2 py-1 text-body2">
          {scorecards.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <Input type="number" min={0} max={100} value={score} aria-label="得分"
          onChange={(e) => setScore(Number(e.target.value))} className="w-20" />
        <Input placeholder="标签 excellent/violation/..." value={tags}
          onChange={(e) => setTags(e.target.value)} className="w-44" />
        <Input placeholder="备注" value={comment}
          onChange={(e) => setComment(e.target.value)} className="w-60" />
        <Button size="md" onClick={submit} disabled={!scid}>提交质检</Button>
      </div>
    </Card>
  );
}

function ReviewsList({ rows }: { rows: QaReview[] }) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">时间</th>
            <th className="px-3 py-2 text-left font-normal">会话</th>
            <th className="px-3 py-2 text-left font-normal">质检员</th>
            <th className="px-3 py-2 text-right font-normal">得分</th>
            <th className="px-3 py-2 text-left font-normal">标签</th>
            <th className="px-3 py-2 text-left font-normal">备注</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">暂无记录</td></tr>
          )}
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-tertiary">{r.created_at}</td>
              <td className="px-3 py-2 text-ink-primary">#{r.conversation_id}</td>
              <td className="px-3 py-2 text-ink-secondary">{r.reviewer_staff_id}</td>
              <td className="px-3 py-2 text-right text-ink-primary">{r.score}</td>
              <td className="px-3 py-2 text-ink-secondary">{r.tags ?? "—"}</td>
              <td className="px-3 py-2 text-ink-tertiary">{r.comment ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function QaReviewRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [search] = useSearchParams();
  const defaultConvId = Number(search.get("conversation_id") ?? 0);
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [reviews, setReviews] = useState<QaReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([
      listScorecards(token, true),
      listReviews(token, defaultConvId ? { conversation_id: defaultConvId } : undefined),
    ])
      .then(([sc, rv]) => { setScorecards(sc); setReviews(rv); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="会话质检" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <ScorecardCreator onCreated={reload} onError={setErr} />
            <ReviewForm scorecards={scorecards} defaultConvId={defaultConvId || 1}
              onSubmitted={reload} onError={setErr} />
            <ReviewsList rows={reviews} />
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `QaReviewRoute`，在 StaffLayout 块内加 `<Route path="/admin/qa" element={<QaReviewRoute />} />`。

- [ ] **Step 4: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminQa.ts src/routes/admin/QaReviewRoute.tsx src/App.tsx`
Expected: typecheck pass；新增 3 个文件 eslint 0 problems。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminQa.ts web/src/routes/admin/QaReviewRoute.tsx web/src/App.tsx
git commit -m "feat(admin): 会话质检前端页（评分卡 + 提交 + 列表）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 2 — 客服满意度（采集 + 后台聚合）

## Task 2.1: agent_ratings 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

在 `server/src/ai_engine/persistence/schema.py` 末尾追加：
```python
# 用户对人工客服的满意度评分（区别于 message_feedback 是对 AI 的 👍👎）
agent_ratings = Table(
    "agent_ratings",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("staff_id", String(64), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("user_type", String(8), nullable=False),
    Column("rating", Integer, nullable=False),  # 1-5
    Column("comment", Text),
    Column("created_at", String(32), nullable=False),
    CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_rating_range"),
)
Index("idx_agent_ratings_staff", agent_ratings.c.staff_id, agent_ratings.c.created_at)
Index("idx_agent_ratings_conv", agent_ratings.c.conversation_id)
```

- [ ] **Step 2: parity FAIL → 建迁移 → parity PASS**

`cd server && alembic revision -m "agent_ratings"`，编辑生成的文件：
```python
def upgrade() -> None:
    op.create_table(
        "agent_ratings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("user_type", sa.String(8), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_rating_range"),
    )
    op.create_index("idx_agent_ratings_staff", "agent_ratings", ["staff_id", "created_at"])
    op.create_index("idx_agent_ratings_conv", "agent_ratings", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("idx_agent_ratings_conv", table_name="agent_ratings")
    op.drop_index("idx_agent_ratings_staff", table_name="agent_ratings")
    op.drop_table("agent_ratings")
```
Run: `cd server && python -m pytest tests/test_alembic_migrations.py -v` → 2 pass，单 head。

- [ ] **Step 3: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git commit -m "feat(admin): agent_ratings 表 + 迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: agent_ratings persistence

**Files:**
- Create: `server/src/ai_engine/persistence/agent_ratings.py`
- Test: `server/tests/test_agent_ratings_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_agent_ratings_dao.py
from ai_engine.persistence import agent_ratings


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_record_and_get(temp_db_url):
    await _init(temp_db_url)
    rid = await agent_ratings.record(
        conversation_id=1, staff_id="AG1", subject_id="u1",
        user_type="c", rating=5, comment="赞",
    )
    assert rid > 0
    row = await agent_ratings.get_for_conversation(conversation_id=1, subject_id="u1")
    assert row is not None and row["rating"] == 5


async def test_get_for_conversation_isolation(temp_db_url):
    """不同 subject_id 不能读到他人评分。"""
    await _init(temp_db_url)
    await agent_ratings.record(1, "AG1", "u1", "c", 5, None)
    row = await agent_ratings.get_for_conversation(conversation_id=1, subject_id="u_other")
    assert row is None


async def test_aggregate_by_staff(temp_db_url):
    await _init(temp_db_url)
    await agent_ratings.record(1, "AG1", "u1", "c", 5, None)
    await agent_ratings.record(2, "AG1", "u2", "c", 3, None)
    await agent_ratings.record(3, "AG2", "u3", "c", 4, None)
    agg = await agent_ratings.aggregate_by_staff("AG1")
    assert agg["count"] == 2
    assert agg["avg_rating"] == 4.0
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_agent_ratings_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/agent_ratings.py
"""用户对人工客服的满意度评分（1-5 星，会话维度，subject 强隔离）。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def record(
    conversation_id: int,
    staff_id: str,
    subject_id: str,
    user_type: str,
    rating: int,
    comment: str | None,
) -> int:
    if rating < 1 or rating > 5:
        raise ValueError("rating must be 1..5")
    return await db.insert_returning_id(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, comment, created_at) "
        "VALUES (:cid, :sid, :subj, :ut, :rating, :cmt, :now) RETURNING id",
        {
            "cid": int(conversation_id), "sid": staff_id, "subj": subject_id,
            "ut": user_type, "rating": int(rating), "cmt": comment, "now": now_str(),
        },
    )


async def get_for_conversation(
    conversation_id: int, subject_id: str
) -> dict[str, Any] | None:
    """同会话同 subject 的评分（用于查询是否已评过）。"""
    return await db.fetch_one(
        "SELECT id, rating, comment, created_at FROM agent_ratings "
        "WHERE conversation_id = :cid AND subject_id = :subj "
        "ORDER BY id DESC LIMIT 1",
        {"cid": int(conversation_id), "subj": subject_id},
    )


async def aggregate_by_staff(
    staff_id: str, date_from: str | None = None, date_to: str | None = None
) -> dict[str, Any]:
    row = await db.fetch_one(
        "SELECT COUNT(*) AS n, AVG(rating) AS avg_rating FROM agent_ratings "
        "WHERE staff_id = :sid "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt)",
        {"sid": staff_id, "df": date_from, "dt": date_to},
    )
    return {
        "count": int(row["n"]) if row and row["n"] is not None else 0,
        "avg_rating": float(row["avg_rating"]) if row and row["avg_rating"] is not None else 0.0,
    }


async def list_for_admin(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, conversation_id, staff_id, user_type, rating, comment, created_at "
        "FROM agent_ratings "
        "WHERE (CAST(:sid AS TEXT) IS NULL OR staff_id = :sid) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {"sid": staff_id, "df": date_from, "dt": date_to, "lim": limit, "off": offset},
    )
```

- [ ] **Step 4: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_agent_ratings_dao.py -v` (3 pass)
Run: `cd server && ruff check src/ai_engine/persistence/agent_ratings.py tests/test_agent_ratings_dao.py` clean。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/agent_ratings.py server/tests/test_agent_ratings_dao.py
git commit -m "feat(admin): 客服满意度 persistence（记录/查询/按客服聚合）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.3: 满意度采集 + 后台聚合 API

**Files:**
- Create: `server/src/ai_engine/api/agent_ratings.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_agent_ratings_api.py`

设计两类端点同放一个文件：
- 用户端（C/B 端用户主动评分，需会话归属校验）：`POST /api/v1/conversations/{conv_id}/agent-rating`、`GET /api/v1/conversations/{conv_id}/agent-rating/eligibility`。
- 后台聚合（supervisor/manager/admin 看）：`GET /admin/api/v1/agent-ratings`。

用户端鉴权用现有 `require_subject`（如果项目里没有这种通用依赖，本 task 直接复用现有 conversations 路由的鉴权 helper——参照 `server/src/ai_engine/api/conversations.py` 怎么读取 subject_id；若需要在此 task 新建 helper，新建一个最小的 `_resolve_subject(request)` 内联函数即可，不要重构其它代码）。

"eligibility" 判定：会话必须存在；该 subject 拥有该会话；该会话有过人工接管（`conversations.mode IN ('human_takeover','human_pending')` 至少一次 OR `staff_actions.action='take'` 存在）；该 subject 还没评过分。返回 `{eligible, already_rated, staff_id}`，前端据此决定是否显示按钮。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_agent_ratings_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    # 准备一通有客服接管历史的会话（user_type=b 走 X-BU-ID 鉴权方便测试）
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, assigned_staff_id, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', 'AG1', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:01:00')"
    )
    yield {"sup": issue_staff_token("SUP1", "supervisor")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_eligibility_for_taken_conversation(env):
    async with await _c() as c:
        r = await c.get("/api/v1/conversations/1/agent-rating/eligibility",
                        headers={"X-BU-ID": "BU1"})
    assert r.status_code == 200
    body = r.json()
    assert body["eligible"] is True
    assert body["already_rated"] is False
    assert body["staff_id"] == "AG1"


async def test_eligibility_wrong_subject_403(env):
    async with await _c() as c:
        r = await c.get("/api/v1/conversations/1/agent-rating/eligibility",
                        headers={"X-BU-ID": "BU_OTHER"})
    assert r.status_code == 403


async def test_submit_rating_and_become_already_rated(env):
    async with await _c() as c:
        r = await c.post("/api/v1/conversations/1/agent-rating",
                         json={"rating": 5, "comment": "赞"},
                         headers={"X-BU-ID": "BU1"})
        assert r.status_code == 200
        elig = (await c.get("/api/v1/conversations/1/agent-rating/eligibility",
                            headers={"X-BU-ID": "BU1"})).json()
    assert elig["already_rated"] is True


async def test_admin_aggregate(env):
    async with await _c() as c:
        await c.post("/api/v1/conversations/1/agent-rating",
                     json={"rating": 4, "comment": "OK"},
                     headers={"X-BU-ID": "BU1"})
        r = await c.get("/admin/api/v1/agent-ratings?staff_id=AG1",
                        headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert body["aggregate"]["count"] == 1
    assert body["aggregate"]["avg_rating"] == 4.0
    assert any(it["rating"] == 4 for it in body["items"])


async def test_admin_agent_forbidden(env):
    from ai_engine.auth.staff_session import issue_staff_token
    agent_token = issue_staff_token("AG_X", "agent")
    async with await _c() as c:
        r = await c.get("/admin/api/v1/agent-ratings", headers=_h(agent_token))
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_agent_ratings_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/agent_ratings.py
"""客服满意度：C/B 端用户提交 + 后台聚合查询。

用户端鉴权：C 端走 c_session（Cookie），B 端走 bu_session 或 DEV_TRUST_BU_HEADER。
本文件用一个最小 _resolve_subject 内联依赖：先尝试 BU header（测试/B 端），再尝试 C session。
"""

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, agent_ratings, db

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


async def _resolve_subject(
    request: Request, x_bu_id: str = Header(default="")
) -> tuple[str, str]:
    """返回 (subject_id, user_type)。生产请按项目鉴权配置完善 C 端走 c_session 的分支。"""
    from ai_engine.config import settings
    if settings.dev_trust_bu_header and x_bu_id:
        return x_bu_id, "b"
    # C 端：尝试从 c_session 读 userCode（按项目现有方式；空则 401）
    try:
        from ai_engine.auth.c_session import resolve_subject_from_request  # 若存在
        subj = await resolve_subject_from_request(request)
        if subj:
            return subj, "c"
    except ImportError:
        pass
    raise HTTPException(401, "no subject")


async def _conv_belongs_to(subject_id: str, user_type: str, conv_id: int) -> bool:
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM conversations WHERE id = :id AND subject_id = :s AND user_type = :ut",
        {"id": conv_id, "s": subject_id, "ut": user_type},
    )
    return row is not None


async def _conv_assigned_staff(conv_id: int) -> str | None:
    row = await db.fetch_one(
        "SELECT assigned_staff_id, mode FROM conversations WHERE id = :id",
        {"id": conv_id},
    )
    if row is None:
        return None
    if row["assigned_staff_id"]:
        return str(row["assigned_staff_id"])
    # 若 assigned 已清空，回退到最近一次 take 的 staff
    take = await db.fetch_one(
        "SELECT staff_id FROM staff_actions WHERE conversation_id = :cid AND action = 'take' "
        "ORDER BY id DESC LIMIT 1",
        {"cid": conv_id},
    )
    return str(take["staff_id"]) if take else None


@router.get("/api/v1/conversations/{conv_id}/agent-rating/eligibility")
async def eligibility(
    conv_id: int,
    request: Request,
    x_bu_id: str = Header(default=""),
) -> dict[str, Any]:
    subj, ut = await _resolve_subject(request, x_bu_id)
    if not await _conv_belongs_to(subj, ut, conv_id):
        raise HTTPException(403, "not your conversation")
    staff_id = await _conv_assigned_staff(conv_id)
    if not staff_id:
        return {"eligible": False, "already_rated": False, "staff_id": None}
    existing = await agent_ratings.get_for_conversation(conv_id, subj)
    return {
        "eligible": True,
        "already_rated": existing is not None,
        "staff_id": staff_id,
    }


class RatingIn(BaseModel):
    rating: int
    comment: str | None = None


@router.post("/api/v1/conversations/{conv_id}/agent-rating")
async def submit(
    conv_id: int,
    body: RatingIn,
    request: Request,
    x_bu_id: str = Header(default=""),
) -> dict[str, Any]:
    subj, ut = await _resolve_subject(request, x_bu_id)
    if not await _conv_belongs_to(subj, ut, conv_id):
        raise HTTPException(403, "not your conversation")
    staff_id = await _conv_assigned_staff(conv_id)
    if not staff_id:
        raise HTTPException(400, "no agent assigned")
    existing = await agent_ratings.get_for_conversation(conv_id, subj)
    if existing is not None:
        raise HTTPException(409, "already rated")
    try:
        rid = await agent_ratings.record(
            conversation_id=conv_id, staff_id=staff_id, subject_id=subj,
            user_type=ut, rating=body.rating, comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "id": rid}


# ── 后台聚合 ──────────────────────────────────────────────────────────────

@router.get("/admin/api/v1/agent-ratings")
async def admin_list(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    items = await agent_ratings.list_for_admin(
        staff_id=staff_id, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    aggregate = {"count": 0, "avg_rating": 0.0}
    if staff_id:
        aggregate = await agent_ratings.aggregate_by_staff(staff_id, date_from, date_to)
    return {"items": items, "aggregate": aggregate}
```

注：上面文件 `admin_audit` 实际未用，移除该 import 以免 ruff F401：把 `from ai_engine.persistence import admin_audit, agent_ratings, db` 改为 `from ai_engine.persistence import agent_ratings, db`。

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.agent_ratings import router as agent_ratings_router` + `app.include_router(agent_ratings_router)`。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_agent_ratings_api.py -v` (5 pass)
Run: `cd server && ruff check src/ai_engine/api/agent_ratings.py src/ai_engine/main.py tests/test_agent_ratings_api.py` clean。
若 ruff 报 F401 admin_audit 未用，按 Step 3 末尾指示移除该 import。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/agent_ratings.py server/src/ai_engine/main.py server/tests/test_agent_ratings_api.py
git commit -m "feat(admin): 客服满意度采集 + 后台聚合 API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.4: C 端采集 UI（独立组件 + 挂 ChatRoute）

**Files:**
- Create: `web/src/api/userAgentRating.ts`
- Create: `web/src/components/AgentRatingButton.tsx`
- Modify: `web/src/routes/ChatRoute.tsx`（**先 `git status` 确认本文件非脏**；若 ChatRoute.tsx 也脏了，挂载点改为新建 `web/src/components/AgentRatingMount.tsx` 由它读路由 + 渲染按钮，并在某个干净的入口挂载——本 task 默认 ChatRoute.tsx 干净）

设计：用户主动触发的"评价此客服服务"按钮，固定在聊天区右上角；按钮按 `eligibility` 接口决定是否显示；点击弹 1-5 星 + 备注，提交后隐藏自身。会话 ID 通过 props 从 ChatRoute 传入（已在 ChatRoute 里被现有逻辑持有，或读 `lib/chatSession.ts`）。

- [ ] **Step 1: 确认 ChatRoute.tsx 干净**

Run: `git status --short web/src/routes/ChatRoute.tsx`
Expected: 无输出（文件不在 modified 列表）。
若有输出：跳过本 task 的"修改 ChatRoute"步骤，新建 `AgentRatingMount.tsx` 但不挂载（留待用户自己挂），把这一情况写进 commit message 备注。

- [ ] **Step 2: API client**

```typescript
// web/src/api/userAgentRating.ts
export type RatingEligibility = {
  eligible: boolean;
  already_rated: boolean;
  staff_id: string | null;
};

/** 走默认 fetch（不用 staffFetch，因为这是 C/B 端用户接口，不是 staff token）。
 * 401 不自动登出（C 端有自己的登录引导路径）。 */
export async function getRatingEligibility(conversationId: number): Promise<RatingEligibility> {
  const r = await fetch(`/api/v1/conversations/${conversationId}/agent-rating/eligibility`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`eligibility ${r.status}`);
  return r.json();
}

export async function submitAgentRating(
  conversationId: number,
  body: { rating: number; comment?: string },
): Promise<void> {
  const r = await fetch(`/api/v1/conversations/${conversationId}/agent-rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `rate ${r.status}`);
  }
}
```

- [ ] **Step 3: 评分按钮组件**

```tsx
// web/src/components/AgentRatingButton.tsx
import { useEffect, useState } from "react";

import { getRatingEligibility, submitAgentRating } from "../api/userAgentRating";

function Stars({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="评分">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" role="radio" aria-checked={value === n}
          onClick={() => onChange(n)}
          className={value >= n ? "text-status-warning" : "text-ink-tertiary"}>
          ★
        </button>
      ))}
    </div>
  );
}

function RatingDialog({ onClose, onDone, conversationId }: {
  onClose: () => void; onDone: () => void; conversationId: number;
}) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  async function submit() {
    setErr("");
    try {
      await submitAgentRating(conversationId, { rating, comment: comment || undefined });
      onDone();
    } catch (e) { setErr(e instanceof Error ? e.message : "提交失败"); }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="w-80 rounded-md bg-surface-card p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 text-sh2 text-ink-primary">评价本次客服</div>
        <Stars value={rating} onChange={setRating} />
        <textarea className="mt-2 w-full rounded border border-line px-2 py-1 text-body3"
          rows={3} placeholder="留言（可选）"
          value={comment} onChange={(e) => setComment(e.target.value)} />
        {err && <div className="mt-1 text-footnote text-status-error">{err}</div>}
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="rounded px-3 py-1 text-body3 text-ink-secondary">取消</button>
          <button onClick={submit} className="rounded bg-brand px-3 py-1 text-body3 text-ink-onbrand">提交</button>
        </div>
      </div>
    </div>
  );
}

export function AgentRatingButton({ conversationId }: { conversationId: number | null }) {
  const [eligible, setEligible] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (conversationId == null || conversationId <= 0) return;
    let cancelled = false;
    getRatingEligibility(conversationId)
      .then((e) => { if (!cancelled) setEligible(e.eligible && !e.already_rated); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [conversationId]);

  if (!eligible || conversationId == null) return null;
  return (
    <>
      <button onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 rounded-full bg-brand px-3 py-2 text-body3 text-ink-onbrand shadow-md md:bottom-6"
        aria-label="评价客服">
        评价客服
      </button>
      {open && (
        <RatingDialog conversationId={conversationId}
          onClose={() => setOpen(false)}
          onDone={() => { setOpen(false); setEligible(false); }} />
      )}
    </>
  );
}
```

- [ ] **Step 4: 挂到 ChatRoute（前提：Step 1 确认其干净）**

读 `web/src/routes/ChatRoute.tsx`，找到 ChatRoute 顶层 return 的 JSX。在最外层片段里加 `<AgentRatingButton conversationId={<现有 conversation id 变量>} />`——会话 ID 变量从该文件已有的 hooks/state 中取（grep `conversation_id` 或 `convId`/`sessionId` 定位；如果没有现成变量，从 `web/src/lib/chatSession.ts` 读 `getChatSession()`）。
保留其它代码不动。

- [ ] **Step 5: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/userAgentRating.ts src/components/AgentRatingButton.tsx src/routes/ChatRoute.tsx`
Expected: typecheck pass；新增 2 文件 eslint 0 problems；ChatRoute.tsx 不引入新 warning。

- [ ] **Step 6: Commit**

```bash
git add web/src/api/userAgentRating.ts web/src/components/AgentRatingButton.tsx web/src/routes/ChatRoute.tsx
git commit -m "feat(c-end): 客服满意度采集按钮（用户主动触发，弹窗 1-5 星）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
若 Step 1 显示 ChatRoute.tsx 脏，本 task 仅提交新建的 2 文件，commit message 末尾加："ChatRoute.tsx 因预存改动未挂载，需用户后续手动加 `<AgentRatingButton conversationId={...} />`"。

---

# Phase 3 — 客服绩效详情

## Task 3.1: staff_performance persistence

**Files:**
- Create: `server/src/ai_engine/persistence/staff_performance.py`
- Test: `server/tests/test_staff_performance_dao.py`

设计：一个 `compute_performance(staff_id, date_from, date_to)` 返回 dict，含：takeovers / resolved / release_ratio / avg_handle_seconds（这部分复用 `staff_metrics.compute_kpi` 的逻辑）+ 满意度 `agent_ratings.aggregate_by_staff` + 质检 `admin_qa.avg_score_by_reviewer`。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_staff_performance_dao.py
from ai_engine.persistence import staff_performance


async def _seed_one_takeover(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:00:00'), "
        "(1, 'AG1', 'resolved', '2026-05-30 00:05:00')"
    )


async def test_perf_basic_kpi(temp_db_url):
    await _seed_one_takeover(temp_db_url)
    p = await staff_performance.compute_performance("AG1", None, None)
    assert p["takeovers"] == 1
    assert p["resolved"] == 1
    assert p["avg_handle_seconds"] >= 0
    assert p["satisfaction"] == {"count": 0, "avg_rating": 0.0}
    assert p["qa"] == {"count": 0, "avg_score": 0.0}


async def test_perf_with_rating_and_qa(temp_db_url):
    from ai_engine.persistence import admin_qa, agent_ratings
    await _seed_one_takeover(temp_db_url)
    await agent_ratings.record(1, "AG1", "BU1", "b", 5, None)
    sid = await admin_qa.create_scorecard("c", [])
    await admin_qa.submit_review(1, "AG1", sid, 90, {})
    p = await staff_performance.compute_performance("AG1", None, None)
    assert p["satisfaction"]["count"] == 1 and p["satisfaction"]["avg_rating"] == 5.0
    assert p["qa"]["count"] == 1 and p["qa"]["avg_score"] == 90.0
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_staff_performance_dao.py -v`
Expected: ModuleNotFoundError staff_performance。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/staff_performance.py
"""单客服绩效详情聚合：复用 staff_metrics 的接管/解决/时长 + 满意度 + 质检均分。"""

from typing import Any

from ai_engine.persistence import admin_qa, agent_ratings, staff_metrics


async def compute_performance(
    staff_id: str, date_from: str | None, date_to: str | None
) -> dict[str, Any]:
    kpi_rows = await staff_metrics.compute_kpi(date_from, date_to)
    base: dict[str, Any] = {
        "staff_id": staff_id,
        "takeovers": 0, "releases": 0, "resolved": 0, "transfers": 0,
        "release_ratio": 0.0, "resolved_ratio": 0.0, "transfer_ratio": 0.0,
        "avg_handle_seconds": 0.0,
    }
    for row in kpi_rows:
        if row.get("staff_id") == staff_id:
            base.update({k: row[k] for k in (
                "takeovers", "releases", "resolved", "transfers",
                "release_ratio", "resolved_ratio", "transfer_ratio", "avg_handle_seconds",
            )})
            break
    base["satisfaction"] = await agent_ratings.aggregate_by_staff(staff_id, date_from, date_to)
    base["qa"] = await admin_qa.avg_score_by_reviewer(staff_id, date_from, date_to)
    return base
```

- [ ] **Step 4: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_staff_performance_dao.py -v` (2 pass)
Run: `cd server && ruff check src/ai_engine/persistence/staff_performance.py tests/test_staff_performance_dao.py` clean。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/staff_performance.py server/tests/test_staff_performance_dao.py
git commit -m "feat(admin): 客服绩效详情聚合（KPI + 满意度 + 质检均分）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: 客服绩效详情 API

**Files:**
- Create: `server/src/ai_engine/api/admin_staff_performance.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_staff_performance_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_staff_performance_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:00:00'), "
        "(1, 'AG1', 'resolved', '2026-05-30 00:05:00')"
    )
    yield {"sup": issue_staff_token("SUP1", "supervisor"),
           "ag": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/staff/AG1/performance", headers=_h(env["ag"]))
    assert r.status_code == 403


async def test_sup_performance(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/staff/AG1/performance", headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert body["staff_id"] == "AG1"
    assert body["takeovers"] == 1
    assert "satisfaction" in body and "qa" in body
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_admin_staff_performance_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_staff_performance.py
"""单客服绩效详情（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence.staff_performance import compute_performance

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/staff/{staff_id}/performance")
async def get_performance(
    staff_id: str,
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return await compute_performance(staff_id, date_from, date_to)
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_staff_performance import router as admin_staff_perf_router` + `app.include_router(admin_staff_perf_router)`。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_staff_performance_api.py -v` (2 pass)
Run: `cd server && ruff check src/ai_engine/api/admin_staff_performance.py src/ai_engine/main.py tests/test_admin_staff_performance_api.py` clean。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_staff_performance.py server/src/ai_engine/main.py server/tests/test_admin_staff_performance_api.py
git commit -m "feat(admin): 客服绩效详情 API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: 客服绩效详情前端页 + 从账号页跳转

**Files:**
- Create: `web/src/api/adminStaffPerformance.ts`
- Create: `web/src/routes/admin/StaffPerformanceRoute.tsx`
- Modify: `web/src/App.tsx`（注册路由）
- Modify: `web/src/routes/admin/StaffAccountsRoute.tsx`（每行加"绩效"链接）

设计：路由 `/admin/performance` 列表页（按 staff_id 选择）+ 详情页 `/admin/performance/:staffId`（直接传入）。务实做法：单页面，URL 参数选 staff_id；账号页直接跳详情。

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminStaffPerformance.ts
import { staffFetch } from "./staffFetch";

export type StaffPerformance = {
  staff_id: string;
  takeovers: number;
  releases: number;
  resolved: number;
  transfers: number;
  release_ratio: number;
  resolved_ratio: number;
  transfer_ratio: number;
  avg_handle_seconds: number;
  satisfaction: { count: number; avg_rating: number };
  qa: { count: number; avg_score: number };
};

export async function getPerformance(
  token: string, staffId: string, opts?: { from?: string; to?: string },
): Promise<StaffPerformance> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(
    `/admin/api/v1/staff/${staffId}/performance?${qs.toString()}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!r.ok) throw new Error(`performance ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/StaffPerformanceRoute.tsx
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { getPerformance, type StaffPerformance } from "../../api/adminStaffPerformance";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <div className="flex flex-col gap-1 px-page py-block">
        <span className="text-footnote text-ink-secondary">{label}</span>
        <span className="text-h3 text-ink-primary">{value}</span>
      </div>
    </Card>
  );
}

function StatsGrid({ p }: { p: StaffPerformance }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      <Stat label="接管数" value={p.takeovers} />
      <Stat label="解决数" value={p.resolved} />
      <Stat label="转派数" value={p.transfers} />
      <Stat label="平均处理(秒)" value={Math.round(p.avg_handle_seconds)} />
      <Stat label="满意度(均/数)"
        value={`${p.satisfaction.avg_rating.toFixed(1)} / ${p.satisfaction.count}`} />
      <Stat label="质检均分(分/数)"
        value={`${p.qa.avg_score.toFixed(1)} / ${p.qa.count}`} />
    </div>
  );
}

export function StaffPerformanceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const { staffId: paramStaffId } = useParams();
  const [search, setSearch] = useSearchParams();
  const [staffId, setStaffId] = useState(paramStaffId ?? search.get("staff_id") ?? "");
  const [p, setP] = useState<StaffPerformance | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); return; }
    if (!staffId) return;
    setLoading(true); setErr("");
    getPerformance(token, staffId)
      .then(setP)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, staffId]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服绩效详情" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <Input placeholder="staff_id" value={staffId}
              onChange={(e) => setStaffId(e.target.value)} className="w-44" />
            <button className="rounded bg-brand px-3 py-1 text-body3 text-ink-onbrand"
              onClick={() => { setSearch({ staff_id: staffId }); }}>
              查询
            </button>
          </div>
        </Card>
      )}
      {loading ? <LoadingState /> : p && <StatsGrid p={p} />}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 账号页跳转**

`web/src/App.tsx`：import `StaffPerformanceRoute`，StaffLayout 块内加：
```tsx
<Route path="/admin/performance" element={<StaffPerformanceRoute />} />
<Route path="/admin/performance/:staffId" element={<StaffPerformanceRoute />} />
```

`web/src/routes/admin/StaffAccountsRoute.tsx`：在每行 staff 的操作单元格加一个跳链接 `<Link to={`/admin/performance/${s.staff_id}`} className="text-brand">绩效</Link>`（与"停用/启用/重置密码"按钮并列，import `Link` from `"react-router-dom"`）。仅追加这一个链接，不动其它代码。

- [ ] **Step 4: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminStaffPerformance.ts src/routes/admin/StaffPerformanceRoute.tsx src/App.tsx src/routes/admin/StaffAccountsRoute.tsx`
Expected: typecheck pass；自己改/建的 4 文件 eslint 0 problems。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminStaffPerformance.ts web/src/routes/admin/StaffPerformanceRoute.tsx web/src/App.tsx web/src/routes/admin/StaffAccountsRoute.tsx
git commit -m "feat(admin): 客服绩效详情前端页 + 账号页跳转链接

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 4 — AI 工具权限矩阵（最大改动：接入既有工具路由）

## Task 4.1: tool_policies 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

在 `schema.py` 末尾追加：
```python
# AI 工具按角色的策略：是否允许 / 是否可解锁脱敏。
# (tool_name, role) 唯一；表为空时回退到代码默认（M2 平滑过渡）。
tool_policies = Table(
    "tool_policies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tool_name", String(64), nullable=False),
    Column("role", String(32), nullable=False),
    Column("allowed", Integer, nullable=False, server_default="0"),  # 0/1
    Column("unmask_allowed", Integer, nullable=False, server_default="0"),  # 0/1
    Column("updated_by", String(64)),
    Column("updated_at", String(32), nullable=False),
)
Index("ux_tool_policy_role", tool_policies.c.tool_name, tool_policies.c.role, unique=True)
```

- [ ] **Step 2: 建迁移 + 跑 parity**

Run: `cd server && alembic revision -m "tool_policies"`
编辑生成的文件：
```python
def upgrade() -> None:
    op.create_table(
        "tool_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unmask_allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index(
        "ux_tool_policy_role", "tool_policies", ["tool_name", "role"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ux_tool_policy_role", table_name="tool_policies")
    op.drop_table("tool_policies")
```
Run: `cd server && python -m pytest tests/test_alembic_migrations.py -v` → 2 pass，单 head。

- [ ] **Step 3: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git commit -m "feat(admin): tool_policies 表 + 迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.2: tool_policies persistence（含内存缓存 + 默认回退）

**Files:**
- Create: `server/src/ai_engine/persistence/tool_policies.py`
- Test: `server/tests/test_tool_policies_dao.py`

设计要点：
- `is_tool_allowed(tool_name, role) -> bool`：先查 DB；若 (tool, role) 行不存在，回退到代码默认（`_DEFAULTS`）；M2 默认 = 与既有 `_STAFF_TOOL_WHITELIST` 相同。
- `is_unmask_allowed(tool_name, role) -> bool`：先查 DB；若不存在回退到代码默认 = `role == "engineer"`（与既有 `dispatch` 默认一致）。
- 内存缓存：模块级 dict `_CACHE`；调用 `invalidate_cache()` 由写 API 触发；缓存命中时无 DB 读。
- `list_all() / upsert_many()`：API 用。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_tool_policies_dao.py
from ai_engine.persistence import tool_policies


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()


async def test_default_fallback_when_empty(temp_db_url):
    """表空时：受 STAFF 默认白名单覆盖的工具+角色返回 True，其它返回 False。"""
    await _init(temp_db_url)
    # 既有默认：query_user 在 _STAFF_TOOL_WHITELIST；agent 允许调
    assert await tool_policies.is_tool_allowed("query_user", "agent") is True
    # 不在白名单的随便起名字 → False
    assert await tool_policies.is_tool_allowed("dangerous_tool", "agent") is False


async def test_default_unmask_for_engineer(temp_db_url):
    await _init(temp_db_url)
    assert await tool_policies.is_unmask_allowed("query_user", "engineer") is True
    assert await tool_policies.is_unmask_allowed("query_user", "agent") is False


async def test_db_overrides_default(temp_db_url):
    await _init(temp_db_url)
    # 写一行：禁用 query_user / agent
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "agent",
         "allowed": 0, "unmask_allowed": 0},
    ])
    assert await tool_policies.is_tool_allowed("query_user", "agent") is False


async def test_list_all_returns_db_rows(temp_db_url):
    await _init(temp_db_url)
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "senior",
         "allowed": 1, "unmask_allowed": 1},
    ])
    rows = await tool_policies.list_all()
    assert len(rows) == 1 and rows[0]["tool_name"] == "query_user"
    assert int(rows[0]["unmask_allowed"]) == 1
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_tool_policies_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/tool_policies.py
"""AI 工具按角色的策略：先查 DB；缺行回退到代码默认。

代码默认（_DEFAULTS）必须与既有 _STAFF_TOOL_WHITELIST 和 dispatch 的 unmask 规则一致，
保证 M2 上线时即便表空、行为也与 M1 一致；后台后续可在 DB 里改。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

# 与 api/staff_conversations.py 的 _STAFF_TOOL_WHITELIST 一致（默认放行的工具集合）
_STAFF_DEFAULT_TOOLS: set[str] = {
    "query_user", "query_card", "query_kyc", "query_balance", "query_transaction",
    "query_bu_order", "query_bu_request_log", "search_code", "lookup_api_doc", "read_file",
}


def _default_allowed(tool_name: str, role: str) -> bool:
    # M1 既有逻辑：客服(含 senior/engineer/admin)都能代查白名单内工具；
    # supervisor/manager 不参与代查，默认拒。
    if role in {"agent", "senior", "engineer", "admin"}:
        return tool_name in _STAFF_DEFAULT_TOOLS
    return False


def _default_unmask(tool_name: str, role: str) -> bool:
    # M1 既有逻辑：仅 engineer 可解锁脱敏
    return role == "engineer"


# 模块级缓存：键 = (tool_name, role)，值 = (allowed:int, unmask:int) 或 None（未命中 DB）
_CACHE: dict[tuple[str, str], tuple[int, int] | None] = {}


def invalidate_cache() -> None:
    _CACHE.clear()


async def _load_row(tool_name: str, role: str) -> tuple[int, int] | None:
    key = (tool_name, role)
    if key in _CACHE:
        return _CACHE[key]
    row = await db.fetch_one(
        "SELECT allowed, unmask_allowed FROM tool_policies "
        "WHERE tool_name = :t AND role = :r",
        {"t": tool_name, "r": role},
    )
    val = (int(row["allowed"]), int(row["unmask_allowed"])) if row else None
    _CACHE[key] = val
    return val


async def is_tool_allowed(tool_name: str, role: str) -> bool:
    row = await _load_row(tool_name, role)
    if row is None:
        return _default_allowed(tool_name, role)
    return row[0] == 1


async def is_unmask_allowed(tool_name: str, role: str) -> bool:
    row = await _load_row(tool_name, role)
    if row is None:
        return _default_unmask(tool_name, role)
    return row[1] == 1


async def list_all() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT tool_name, role, allowed, unmask_allowed, updated_by, updated_at "
        "FROM tool_policies ORDER BY tool_name, role"
    )


async def upsert_many(actor: str, items: list[dict[str, Any]]) -> int:
    """批量 upsert (tool_name, role, allowed, unmask_allowed)。返回更新条数。

    两库 portable 实现：逐行 SELECT 1 → UPDATE / INSERT。M2 规模可接受。
    """
    n = 0
    now = now_str()
    for it in items:
        tool = str(it["tool_name"])
        role = str(it["role"])
        allowed = int(it.get("allowed", 0))
        unmask = int(it.get("unmask_allowed", 0))
        existing = await db.fetch_one(
            "SELECT id FROM tool_policies WHERE tool_name = :t AND role = :r",
            {"t": tool, "r": role},
        )
        if existing is None:
            await db.execute(
                "INSERT INTO tool_policies(tool_name, role, allowed, unmask_allowed, "
                "updated_by, updated_at) VALUES (:t, :r, :a, :u, :by, :now)",
                {"t": tool, "r": role, "a": allowed, "u": unmask, "by": actor, "now": now},
            )
        else:
            await db.execute(
                "UPDATE tool_policies SET allowed = :a, unmask_allowed = :u, "
                "updated_by = :by, updated_at = :now WHERE id = :id",
                {"a": allowed, "u": unmask, "by": actor, "now": now, "id": existing["id"]},
            )
        n += 1
    invalidate_cache()
    return n
```

- [ ] **Step 4: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_tool_policies_dao.py -v` (4 pass)
Run: `cd server && ruff check src/ai_engine/persistence/tool_policies.py tests/test_tool_policies_dao.py` clean。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/tool_policies.py server/tests/test_tool_policies_dao.py
git commit -m "feat(admin): tool_policies persistence（DB 查询 + 内存缓存 + 默认回退）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.3: 接入既有工具调用前置校验（关键改造）

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py`（**先 git status 确认非脏**）
- Modify: `server/src/ai_engine/agent/tool_router.py`（**先 git status 确认非脏**）
- Test: `server/tests/test_tool_policies_integration.py`

设计：
- `staff_conversations.py:399-422` 客服代查端点：把当前的 `if tool_name not in _STAFF_TOOL_WHITELIST: raise 403` 改为 `if not await tool_policies.is_tool_allowed(tool_name, staff["role"]): raise 403`。
- `staff_conversations.py:421` `dispatch(..., unmask=(staff.get("role")=="engineer"))` 改为 `unmask=await tool_policies.is_unmask_allowed(tool_name, staff["role"])`。
- `agent/tool_router.py` 不强改其默认 unmask 逻辑（AI 自动调用工具时仍用调用方传的 `unmask`）；客服代查那条链由 staff_conversations 全权决定 → 改 staff_conversations 已经足够。

**保守原则**：本 task 只改 staff_conversations.py 两处具体行，不动 tool_router.py。这样：
- AI 自动调用（runtime → dispatch）行为零变化（保持 M1 兼容）。
- 客服代查的"工具白名单 + 脱敏决定"改为读 DB，表空时默认与 M1 相同。

- [ ] **Step 1: 确认目标文件干净**

Run: `git status --short server/src/ai_engine/api/staff_conversations.py server/src/ai_engine/agent/tool_router.py`
Expected: 无输出。
若有 staff_conversations.py 脏（不应该）：BLOCKED 报告，等用户处理。

- [ ] **Step 2: 写失败的集成测试**

```python
# server/tests/test_tool_policies_integration.py
"""客服代查 API 用 DB 中的 tool_policies 决定放行/脱敏；表空走默认。"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db, tool_policies
    from ai_engine.persistence.staff import create_staff
    tool_policies.invalidate_cache()

    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (10, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    yield {"ag": issue_staff_token("AG1", "agent")}
    tool_policies.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_default_whitelist_allows_query_user(env, monkeypatch):
    """表空时 agent 调 query_user 不会被前置校验 403（具体执行可能因业务库未配返回别的错，
    本测试只要求"非 403 因白名单失败"——即必须越过白名单这一关）。"""
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post(
            "/staff/api/v1/conversations/10/ai-tools/query_user",
            json={"user_id": "u1"},
            headers=_h(env["ag"]),
        )
    # 任何非 403 / 非 "tool not allowed" 都算通过白名单；具体业务结果不重要
    assert r.status_code != 403 or "not allowed" not in r.text


async def test_db_override_denies_query_user_for_agent(env):
    """DB 中显式禁用 query_user/agent 后，agent 代查该工具应 403。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence import tool_policies

    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "agent",
         "allowed": 0, "unmask_allowed": 0},
    ])
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post(
            "/staff/api/v1/conversations/10/ai-tools/query_user",
            json={"user_id": "u1"},
            headers=_h(env["ag"]),
        )
    assert r.status_code == 403
```

- [ ] **Step 3: 跑测试 FAIL（DB override 测试 fail）**

Run: `cd server && python -m pytest tests/test_tool_policies_integration.py -v`
Expected: `test_db_override_denies_query_user_for_agent` FAIL（当前 `_STAFF_TOOL_WHITELIST` 是硬编码 set，DB upsert 不会被读到）。

- [ ] **Step 4: 改 staff_conversations.py**

读 `server/src/ai_engine/api/staff_conversations.py`，找到：
1. 文件顶部 import 区——加 `from ai_engine.persistence import tool_policies`。
2. 文件中定义的 `_STAFF_TOOL_WHITELIST = {...}` 常量（≈ 第 381-392 行）——**保留它**（作为代码注释/fallback 来源），但下面的白名单校验改用 DB。
3. 客服代查端点函数（≈ 第 399-422 行，路由 `/staff/api/v1/conversations/{conv_id}/ai-tools/{tool_name}`）：把当前对 `_STAFF_TOOL_WHITELIST` 的成员检查替换为 await `tool_policies.is_tool_allowed(tool_name, role)`；把传给 `dispatch(..., unmask=...)` 的 `unmask` 值改为 await `tool_policies.is_unmask_allowed(tool_name, role)`。

精确替换示例（按当前文件实际代码做最小化 patch，不重排其它内容）：
```python
# 旧（示意，按实际行调整）：
# if tool_name not in _STAFF_TOOL_WHITELIST:
#     raise HTTPException(403, "tool not allowed")
# ...
# result = await dispatch(tool_name, params, unmask=(staff.get("role") == "engineer"), ...)

# 新：
if not await tool_policies.is_tool_allowed(tool_name, str(staff.get("role"))):
    raise HTTPException(403, "tool not allowed")
unmask_flag = await tool_policies.is_unmask_allowed(tool_name, str(staff.get("role")))
result = await dispatch(tool_name, params, unmask=unmask_flag, ...)
```
其它参数照搬现有调用。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_tool_policies_integration.py tests/test_staff_ai_tools.py -v`
Expected: 两个集成测试 pass；既有 `test_staff_ai_tools` 也不退化（默认行为兼容）。
Run: `cd server && ruff check src/ai_engine/api/staff_conversations.py tests/test_tool_policies_integration.py` clean。
Run: `cd server && python -m pytest -k "staff or admin" -v` 跑一遍 staff/admin 相关测试快速回归。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/staff_conversations.py server/tests/test_tool_policies_integration.py
git commit -m "feat(admin): 客服代查工具白名单/脱敏改读 tool_policies（默认与 M1 兼容）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.4: 工具权限矩阵 API + 审计

**Files:**
- Create: `server/src/ai_engine/api/admin_tool_policies.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_tool_policies_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_tool_policies_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.staff import create_staff
    tool_policies.invalidate_cache()

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {"eng": issue_staff_token("EN1", "engineer"),
           "ag": issue_staff_token("AG1", "agent")}
    tool_policies.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        assert (await c.get("/admin/api/v1/tool-policies", headers=_h(env["ag"]))).status_code == 403


async def test_engineer_list_and_upsert(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        assert (await c.get("/admin/api/v1/tool-policies", headers=_h(env["eng"]))).status_code == 200
        r = await c.put(
            "/admin/api/v1/tool-policies",
            json={"items": [
                {"tool_name": "query_user", "role": "senior",
                 "allowed": 1, "unmask_allowed": 1},
            ]},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/tool-policies",
                              headers=_h(env["eng"]))).json()["items"]
    assert any(i["tool_name"] == "query_user" and i["role"] == "senior"
               and int(i["unmask_allowed"]) == 1 for i in listed)
    audits = await admin_audit.list_admin_actions(action="tool_policies.upsert", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_admin_tool_policies_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_tool_policies.py
"""AI 工具权限矩阵（engineer/admin）。写操作落审计 + 清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, tool_policies

router = APIRouter()
_eng = require_roles("engineer", "admin")


@router.get("/admin/api/v1/tool-policies")
async def list_policies(staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    return {"items": await tool_policies.list_all()}


class PolicyItem(BaseModel):
    tool_name: str
    role: str
    allowed: int = 0
    unmask_allowed: int = 0


class UpsertIn(BaseModel):
    items: list[PolicyItem]


@router.put("/admin/api/v1/tool-policies")
async def upsert(body: UpsertIn, staff: dict[str, Any] = Depends(_eng)) -> dict[str, Any]:
    n = await tool_policies.upsert_many(
        actor=staff.get("sub", "unknown"),
        items=[it.model_dump() for it in body.items],
    )
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="tool_policies.upsert",
        target_type="tool_policies", target_id=None,
        detail={"count": n},
    )
    return {"ok": True, "count": n}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_tool_policies import router as admin_tool_policies_router` + `app.include_router(admin_tool_policies_router)`。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_tool_policies_api.py -v` (2 pass)
Run: `cd server && ruff check src/ai_engine/api/admin_tool_policies.py src/ai_engine/main.py tests/test_admin_tool_policies_api.py` clean。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_tool_policies.py server/src/ai_engine/main.py server/tests/test_admin_tool_policies_api.py
git commit -m "feat(admin): 工具权限矩阵 API（list/upsert + 审计 + 缓存失效）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.5: 工具权限矩阵前端页（工具 × 角色矩阵）

**Files:**
- Create: `web/src/api/adminToolPolicies.ts`
- Create: `web/src/routes/admin/ToolPoliciesRoute.tsx`
- Modify: `web/src/App.tsx`

设计：表格 = 工具行 × 角色列；每个单元格两个 checkbox（允许 / 解锁脱敏）。前端有一份"工具名清单"（hardcoded：与后端 `_STAFF_DEFAULT_TOOLS` 同 + 几个其它常见工具 `lookup_error_code`、`query_bu_user`），用户在矩阵里改，"保存"按钮一次性 PUT。角色清单：agent/senior/engineer/supervisor（admin 默认允许全部，矩阵不显示）。

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminToolPolicies.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ToolPolicy = {
  tool_name: string;
  role: string;
  allowed: number;
  unmask_allowed: number;
  updated_by: string | null;
  updated_at: string;
};

export async function listToolPolicies(token: string): Promise<ToolPolicy[]> {
  const r = await staffFetch("/admin/api/v1/tool-policies", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).items;
}

export async function upsertToolPolicies(
  token: string,
  items: { tool_name: string; role: string; allowed: number; unmask_allowed: number }[],
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/tool-policies", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ items }),
  });
  if (!r.ok) throw new Error(`upsert ${r.status}`);
}

export const TOOL_NAMES: string[] = [
  "query_user", "query_card", "query_kyc", "query_balance", "query_transaction",
  "query_bu_user", "query_bu_order", "query_bu_request_log",
  "lookup_api_doc", "lookup_error_code", "search_code", "read_file",
];

export const POLICY_ROLES: string[] = ["agent", "senior", "engineer", "supervisor"];
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/ToolPoliciesRoute.tsx
import { useEffect, useMemo, useState } from "react";

import {
  listToolPolicies, POLICY_ROLES, TOOL_NAMES, type ToolPolicy, upsertToolPolicies,
} from "../../api/adminToolPolicies";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

type CellState = { allowed: number; unmask_allowed: number };
type MatrixState = Record<string, Record<string, CellState>>;  // tool → role → cell

function emptyMatrix(): MatrixState {
  const m: MatrixState = {};
  for (const t of TOOL_NAMES) {
    m[t] = {};
    for (const r of POLICY_ROLES) m[t][r] = { allowed: 0, unmask_allowed: 0 };
  }
  return m;
}

function applyRowsToMatrix(rows: ToolPolicy[]): MatrixState {
  const m = emptyMatrix();
  for (const row of rows) {
    if (m[row.tool_name]?.[row.role]) {
      m[row.tool_name][row.role] = {
        allowed: Number(row.allowed), unmask_allowed: Number(row.unmask_allowed),
      };
    }
  }
  return m;
}

function flatten(m: MatrixState) {
  const out: { tool_name: string; role: string; allowed: number; unmask_allowed: number }[] = [];
  for (const t of TOOL_NAMES) for (const r of POLICY_ROLES) {
    out.push({ tool_name: t, role: r, ...m[t][r] });
  }
  return out;
}

function MatrixTable({ value, onChange }: {
  value: MatrixState; onChange: (next: MatrixState) => void;
}) {
  function setCell(tool: string, role: string, key: keyof CellState, v: number) {
    const next: MatrixState = { ...value, [tool]: { ...value[tool] } };
    next[tool][role] = { ...next[tool][role], [key]: v };
    onChange(next);
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">工具</th>
              {POLICY_ROLES.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}<br/><span className="text-footnote">允许 / 解锁</span></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TOOL_NAMES.map((t) => (
              <tr key={t} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{t}</td>
                {POLICY_ROLES.map((r) => {
                  const cell = value[t][r];
                  return (
                    <td key={r} className="px-3 py-2 text-center">
                      <div className="flex justify-center gap-2">
                        <input type="checkbox" aria-label={`${t}/${r}/allowed`}
                          checked={cell.allowed === 1}
                          onChange={(e) => setCell(t, r, "allowed", e.target.checked ? 1 : 0)} />
                        <input type="checkbox" aria-label={`${t}/${r}/unmask`}
                          checked={cell.unmask_allowed === 1}
                          onChange={(e) => setCell(t, r, "unmask_allowed", e.target.checked ? 1 : 0)} />
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function ToolPoliciesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [matrix, setMatrix] = useState<MatrixState>(emptyMatrix);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    setLoading(true);
    listToolPolicies(token)
      .then((rows) => setMatrix(applyRowsToMatrix(rows)))
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const items = useMemo(() => flatten(matrix), [matrix]);

  async function save() {
    if (!token) return;
    setErr(""); setNotice("");
    try { await upsertToolPolicies(token, items); setNotice("已保存（缓存已刷新）"); }
    catch (e) { setErr(e instanceof Error ? e.message : "保存失败"); }
  }

  return (
    <PageContainer width="wide">
      <PageHeader title="AI 工具权限矩阵" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <MatrixTable value={matrix} onChange={setMatrix} />
            <div className="mt-3"><Button size="md" onClick={save}>保存</Button></div>
            <p className="mt-2 text-footnote text-ink-tertiary">
              admin 角色默认全部允许，不在矩阵中显示。空表回退到 M1 默认白名单。
            </p>
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `ToolPoliciesRoute`，StaffLayout 块内加 `<Route path="/admin/tools" element={<ToolPoliciesRoute />} />`。

- [ ] **Step 4: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminToolPolicies.ts src/routes/admin/ToolPoliciesRoute.tsx src/App.tsx`
Expected: typecheck pass；自己改/建的 3 文件 eslint 0 problems。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminToolPolicies.ts web/src/routes/admin/ToolPoliciesRoute.tsx web/src/App.tsx
git commit -m "feat(admin): AI 工具权限矩阵前端页

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 5 — Token 成本大盘

## Task 5.1: daily_token_usage 加 model 列 + model_pricing 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移
- Test: `server/tests/test_token_usage_with_model.py`

设计要点（务实、保留主键不变以避开 SQLite/PG 主键修改的双库风险）：
- `daily_token_usage` 加列 `model String(32) nullable`。**不修改主键**——表示"按 model 维度的细分"通过新建 `daily_token_usage_by_model` 旁路表实现更安全，但 M2 我们采用最小路径：加列即可，主键保持 (subject_id, user_type, date)，model 作为附加维度由 INSERT 覆盖到最近一次写入的 model。
  - **后果**：同一 subject 同一天用了两个 model（M1 + M2）时，按 model 维度的精确细分会丢失，看到的是最后一次写入的 model。这是 MVP 取舍，留给 M3 解决（拆出 by-model 旁路表）。
  - 大盘聚合按 `model` 列分组时只反映"主要使用模型"，仍能给出粗粒度成本视图。
- 新表 `model_pricing(model, input_price_per_1k, output_price_per_1k, currency, updated_at)`，model 是主键。input/output 单价用 Integer 存"千 token 的金额×10000"（避免浮点，单位 = 万分之 currency 单位）；前端展示时除以 10000。

- [ ] **Step 1: 写失败测试（测加列 + 新表）**

```python
# server/tests/test_token_usage_with_model.py
async def test_daily_token_usage_has_model_column(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, input_tokens, "
        "output_tokens, model) VALUES ('u1', 'b', '2026-05-30', 100, 50, 'claude-sonnet-4-6')"
    )
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id = 'u1'"
    )
    assert row is not None
    assert row["model"] == "claude-sonnet-4-6"


async def test_model_pricing_table_exists(temp_db_url):
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await db.execute(
        "INSERT INTO model_pricing(model, input_price_per_1k_x10000, "
        "output_price_per_1k_x10000, currency, updated_at) "
        "VALUES ('claude-sonnet-4-6', 30000, 150000, 'USD', '2026-05-30 00:00:00')"
    )
    row = await db.fetch_one("SELECT * FROM model_pricing WHERE model='claude-sonnet-4-6'")
    assert row is not None and int(row["input_price_per_1k_x10000"]) == 30000
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_token_usage_with_model.py -v`
Expected: 两个 test 都 FAIL（列/表不存在）。

- [ ] **Step 3: 改 schema.py**

定位文件中 `daily_token_usage` 表定义（≈ 第 139-147 行）。把 Table(...) 内的 Column 列表末尾追加：
```python
    Column("model", String(32)),  # 写入时记录主要使用的模型；M2 加列，不改主键
```

在 `schema.py` 末尾追加：
```python
# 模型单价（M2 成本大盘用）。单价存 "每千 token × 10000"，避免浮点 — 展示时除以 10000。
model_pricing = Table(
    "model_pricing",
    metadata,
    Column("model", String(64), primary_key=True),
    Column("input_price_per_1k_x10000", Integer, nullable=False),
    Column("output_price_per_1k_x10000", Integer, nullable=False),
    Column("currency", String(8), nullable=False, server_default="USD"),
    Column("updated_at", String(32), nullable=False),
)
```

- [ ] **Step 4: 建迁移**

Run: `cd server && alembic revision -m "token_usage_model_and_pricing"`
编辑生成的文件：
```python
def upgrade() -> None:
    op.add_column("daily_token_usage", sa.Column("model", sa.String(32), nullable=True))
    op.create_table(
        "model_pricing",
        sa.Column("model", sa.String(64), primary_key=True),
        sa.Column("input_price_per_1k_x10000", sa.Integer(), nullable=False),
        sa.Column("output_price_per_1k_x10000", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_pricing")
    with op.batch_alter_table("daily_token_usage", recreate="always") as batch_op:
        batch_op.drop_column("model")
```
(downgrade 用 batch recreate 兼容 SQLite。PG 直接 drop_column 即可——batch 在 PG 上也会 fallback 到原生 ALTER。)

- [ ] **Step 5: parity + 单测 PASS**

Run: `cd server && python -m pytest tests/test_alembic_migrations.py tests/test_token_usage_with_model.py -v`
Expected: 4 pass，单 head 指向新 revision。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions/ server/tests/test_token_usage_with_model.py
git commit -m "feat(admin): daily_token_usage 加 model 列 + model_pricing 表 + 迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.2: token 写入路径接入 model

**Files:**
- Modify: `server/src/ai_engine/governance/token_budget.py`（先 git status 确认非脏）
- Modify: `server/src/ai_engine/agent/runtime.py`（先 git status 确认非脏）
- Test: `server/tests/test_token_budget_model.py`

设计：
- `_record(...)` / `check_and_record(...)` 新增 `model: str | None = None` 参数，默认 None 保兼容。
- INSERT/UPSERT SQL 加 `model` 列写入（值取 `:model`）。
- 调用方 `runtime._budget_gate` 把 `model` 变量传入。

- [ ] **Step 1: 确认目标文件干净**

Run: `git status --short server/src/ai_engine/governance/token_budget.py server/src/ai_engine/agent/runtime.py`
Expected: 无输出。若有任一脏 → BLOCKED 报告。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_token_budget_model.py
async def test_record_persists_model(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    allowed, _ = await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    assert allowed is True
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id='BU1' AND user_type='b'"
    )
    assert row is not None
    assert row["model"] == "claude-sonnet-4-6"


async def test_record_without_model_keeps_null(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU2", 10, 5)
    row = await db.fetch_one(
        "SELECT model FROM daily_token_usage WHERE subject_id='BU2' AND user_type='b'"
    )
    assert row is not None
    assert row["model"] is None
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_token_budget_model.py -v`
Expected: 第一个 test FAIL（`check_and_record` 不接受 `model` kwarg）。

- [ ] **Step 4: 改 token_budget.py**

读 `server/src/ai_engine/governance/token_budget.py`。当前 `_record` 与 `check_and_record` 签名：
```python
async def _record(subject_id: str, user_type: str, day: str, in_tok: int, out_tok: int) -> None: ...
async def check_and_record(user_type: str, subject_id: str, in_tok: int, out_tok: int): ...
```
改造步骤（最小改动）：
1. `_record` 末尾加参数 `model: str | None = None`。
2. INSERT 语句加 `model` 列与 `:model` 参数；UPSERT 的 `ON CONFLICT DO UPDATE SET ...` 末尾加 `model = COALESCE(CAST(:model AS TEXT), daily_token_usage.model)`（仅当本次写入提供 model 时覆盖，否则保留旧值）。
3. `_record` 参数 dict 加 `"model": model`。
4. `check_and_record` 签名加 `model: str | None = None`；调用 `_record(...)` 时传 `model=model`。

示意（按当前文件实际语句调整）：
```python
async def _record(
    subject_id: str, user_type: str, day: str,
    in_tok: int, out_tok: int, model: str | None = None,
) -> None:
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) "
        "VALUES (:s, :u, :d, :it, :ot, :model) "
        "ON CONFLICT(subject_id, user_type, date) DO UPDATE SET "
        "input_tokens = daily_token_usage.input_tokens + :it, "
        "output_tokens = daily_token_usage.output_tokens + :ot, "
        "model = COALESCE(CAST(:model AS TEXT), daily_token_usage.model)",
        {"s": subject_id, "u": user_type, "d": day,
         "it": int(in_tok), "ot": int(out_tok), "model": model},
    )


async def check_and_record(
    user_type: str, subject_id: str, in_tok: int, out_tok: int,
    model: str | None = None,
) -> tuple[bool, dict]:
    # ... 既有 budget 检查逻辑保持不动 ...
    await _record(subject_id, user_type, _today(), in_tok, out_tok, model=model)
    # ... 既有返回逻辑 ...
```
保留既有 budget 检查、配额超限、返回的 `(allowed, info)` dict 等逻辑——只在 INSERT/UPSERT 加 model 列与传参链。

- [ ] **Step 5: 改 runtime.py 的调用方传 model**

读 `server/src/ai_engine/agent/runtime.py`。定位 `_budget_gate` 函数中调用 `check_and_record(user_type, subject_id, in_tok, out_tok)` 的那一行（≈ 101 行）。改为：
```python
allowed, info = await check_and_record(user_type, subject_id, in_tok, out_tok, model=model)
```
`model` 变量是函数作用域里已有的（≈ 280 行能拿到 `model`，需通过参数链传到 `_budget_gate` —— 若 `_budget_gate` 当前签名没有 `model`，给它加一个 `model: str | None = None` 参数，且调用方传入 `model`）。**仅在签名加可选参数，不动其它逻辑**。

- [ ] **Step 6: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_token_budget_model.py tests/test_token_budget.py tests/test_cost_guard.py -v`
Expected: 新测试 pass；既有 token_budget / cost_guard 测试不退化。
Run: `cd server && ruff check src/ai_engine/governance/token_budget.py src/ai_engine/agent/runtime.py tests/test_token_budget_model.py` clean。

- [ ] **Step 7: Commit**

```bash
git add server/src/ai_engine/governance/token_budget.py server/src/ai_engine/agent/runtime.py server/tests/test_token_budget_model.py
git commit -m "feat(admin): token 用量记录加 model 维度（不动主键，model 列覆盖式写入）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.3: 成本聚合 persistence + model_pricing CRUD

**Files:**
- Create: `server/src/ai_engine/persistence/admin_cost.py`
- Test: `server/tests/test_admin_cost_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_cost_dao.py
from ai_engine.persistence import admin_cost


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_upsert_and_list_pricing(temp_db_url):
    await _init(temp_db_url)
    await admin_cost.upsert_pricing("claude-sonnet-4-6", 30000, 150000, "USD")
    rows = await admin_cost.list_pricing()
    assert len(rows) == 1
    assert rows[0]["model"] == "claude-sonnet-4-6"
    assert int(rows[0]["input_price_per_1k_x10000"]) == 30000


async def test_usage_by_model_sums_correctly(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 1000, 500, 'claude-sonnet-4-6'), "
        "('u2', 'b', '2026-05-30', 2000, 700, 'claude-sonnet-4-6'), "
        "('u3', 'c', '2026-05-30', 100, 50, 'claude-haiku-4-5')"
    )
    rows = await admin_cost.usage_by_model(None, None)
    by = {r["model"]: r for r in rows}
    assert by["claude-sonnet-4-6"]["input_tokens"] == 3000
    assert by["claude-sonnet-4-6"]["output_tokens"] == 1200
    assert by["claude-haiku-4-5"]["input_tokens"] == 100


async def test_usage_by_model_with_pricing_computes_cost(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 10000, 5000, 'claude-sonnet-4-6')"
    )
    await admin_cost.upsert_pricing("claude-sonnet-4-6", 30000, 150000, "USD")
    rows = await admin_cost.usage_by_model(None, None, with_cost=True)
    row = next(r for r in rows if r["model"] == "claude-sonnet-4-6")
    # input cost = 10000 / 1000 * 30000 / 10000 = 30 USD
    # output cost = 5000 / 1000 * 150000 / 10000 = 75 USD
    assert row["input_cost"] == 30.0
    assert row["output_cost"] == 75.0
    assert row["total_cost"] == 105.0
    assert row["currency"] == "USD"
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_admin_cost_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/admin_cost.py
"""Token 成本聚合 + 模型单价 CRUD。

单价存 'per 1k tokens × 10000'（整数避浮点）。
聚合结果可选 with_cost=True 时换算成 currency 金额。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def upsert_pricing(
    model: str, input_price_x10000: int, output_price_x10000: int, currency: str = "USD"
) -> None:
    existing = await db.fetch_one(
        "SELECT model FROM model_pricing WHERE model = :m", {"m": model}
    )
    now = now_str()
    if existing is None:
        await db.execute(
            "INSERT INTO model_pricing(model, input_price_per_1k_x10000, "
            "output_price_per_1k_x10000, currency, updated_at) "
            "VALUES (:m, :i, :o, :c, :now)",
            {"m": model, "i": int(input_price_x10000),
             "o": int(output_price_x10000), "c": currency, "now": now},
        )
    else:
        await db.execute(
            "UPDATE model_pricing SET input_price_per_1k_x10000 = :i, "
            "output_price_per_1k_x10000 = :o, currency = :c, updated_at = :now "
            "WHERE model = :m",
            {"m": model, "i": int(input_price_x10000),
             "o": int(output_price_x10000), "c": currency, "now": now},
        )


async def list_pricing() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT model, input_price_per_1k_x10000, output_price_per_1k_x10000, "
        "currency, updated_at FROM model_pricing ORDER BY model"
    )


async def usage_by_model(
    date_from: str | None,
    date_to: str | None,
    user_type: str | None = None,
    with_cost: bool = False,
) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT COALESCE(model, '(unknown)') AS model, "
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
        "FROM daily_token_usage "
        "WHERE (CAST(:df AS TEXT) IS NULL OR date >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR date <= :dt) "
        "AND (CAST(:ut AS TEXT) IS NULL OR user_type = :ut) "
        "GROUP BY COALESCE(model, '(unknown)') "
        "ORDER BY model",
        {"df": date_from, "dt": date_to, "ut": user_type},
    )
    result = [
        {
            "model": r["model"],
            "input_tokens": int(r["input_tokens"] or 0),
            "output_tokens": int(r["output_tokens"] or 0),
        }
        for r in rows
    ]
    if not with_cost:
        return result
    pricing_rows = await list_pricing()
    pricing = {p["model"]: p for p in pricing_rows}
    for item in result:
        p = pricing.get(item["model"])
        if p is None:
            item["currency"] = None
            item["input_cost"] = 0.0
            item["output_cost"] = 0.0
            item["total_cost"] = 0.0
            continue
        in_cost = item["input_tokens"] / 1000 * int(p["input_price_per_1k_x10000"]) / 10000
        out_cost = item["output_tokens"] / 1000 * int(p["output_price_per_1k_x10000"]) / 10000
        item["currency"] = p["currency"]
        item["input_cost"] = round(in_cost, 4)
        item["output_cost"] = round(out_cost, 4)
        item["total_cost"] = round(in_cost + out_cost, 4)
    return result
```

- [ ] **Step 4: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_cost_dao.py -v` (3 pass)
Run: `cd server && ruff check src/ai_engine/persistence/admin_cost.py tests/test_admin_cost_dao.py` clean。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/admin_cost.py server/tests/test_admin_cost_dao.py
git commit -m "feat(admin): 成本聚合 + model_pricing CRUD（带单价换算）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.4: 成本大盘 API

**Files:**
- Create: `server/src/ai_engine/api/admin_cost.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_cost_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_cost_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence.staff import create_staff

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 1000, 500, 'claude-sonnet-4-6')"
    )
    yield {"eng": issue_staff_token("EN1", "engineer"),
           "ag": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        assert (await c.get("/admin/api/v1/cost/usage", headers=_h(env["ag"]))).status_code == 403


async def test_usage_by_model(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/cost/usage?with_cost=true", headers=_h(env["eng"]))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["model"] == "claude-sonnet-4-6" for i in items)


async def test_pricing_crud(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.put(
            "/admin/api/v1/cost/pricing",
            json={"model": "claude-sonnet-4-6",
                  "input_price_per_1k_x10000": 30000,
                  "output_price_per_1k_x10000": 150000,
                  "currency": "USD"},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/cost/pricing", headers=_h(env["eng"]))).json()["items"]
    assert any(p["model"] == "claude-sonnet-4-6" for p in listed)
    audits = await admin_audit.list_admin_actions(action="cost.pricing.upsert", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && python -m pytest tests/test_admin_cost_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_cost.py
"""Token 成本大盘（engineer/manager/admin）。pricing 更新落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_cost

router = APIRouter()
_view = require_roles("engineer", "manager", "admin")
_engineer = require_roles("engineer", "admin")  # pricing 编辑限工程/admin


@router.get("/admin/api/v1/cost/usage")
async def usage(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    user_type: str | None = Query(default=None),
    with_cost: bool = Query(default=False),
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    return {"items": await admin_cost.usage_by_model(
        date_from, date_to, user_type=user_type, with_cost=with_cost,
    )}


@router.get("/admin/api/v1/cost/pricing")
async def list_pricing(staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return {"items": await admin_cost.list_pricing()}


class PricingIn(BaseModel):
    model: str
    input_price_per_1k_x10000: int
    output_price_per_1k_x10000: int
    currency: str = "USD"


@router.put("/admin/api/v1/cost/pricing")
async def upsert_pricing(body: PricingIn, staff: dict[str, Any] = Depends(_engineer)) -> dict[str, Any]:
    await admin_cost.upsert_pricing(
        body.model, body.input_price_per_1k_x10000,
        body.output_price_per_1k_x10000, body.currency,
    )
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="cost.pricing.upsert",
        target_type="model_pricing", target_id=body.model,
        detail={"in": body.input_price_per_1k_x10000,
                "out": body.output_price_per_1k_x10000, "cur": body.currency},
    )
    return {"ok": True}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_cost import router as admin_cost_router` + `app.include_router(admin_cost_router)`。

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && python -m pytest tests/test_admin_cost_api.py -v` (3 pass)
Run: `cd server && ruff check src/ai_engine/api/admin_cost.py src/ai_engine/main.py tests/test_admin_cost_api.py` clean。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_cost.py server/src/ai_engine/main.py server/tests/test_admin_cost_api.py
git commit -m "feat(admin): 成本大盘 API（usage by model + pricing CRUD + 审计）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.5: 成本大盘前端页

**Files:**
- Create: `web/src/api/adminCost.ts`
- Create: `web/src/routes/admin/CostRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminCost.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type UsageItem = {
  model: string;
  input_tokens: number;
  output_tokens: number;
  currency?: string | null;
  input_cost?: number;
  output_cost?: number;
  total_cost?: number;
};

export type Pricing = {
  model: string;
  input_price_per_1k_x10000: number;
  output_price_per_1k_x10000: number;
  currency: string;
  updated_at: string;
};

export async function getUsage(
  token: string,
  opts?: { from?: string; to?: string; user_type?: string; with_cost?: boolean },
): Promise<UsageItem[]> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  if (opts?.user_type) qs.set("user_type", opts.user_type);
  if (opts?.with_cost) qs.set("with_cost", "true");
  const r = await staffFetch(`/admin/api/v1/cost/usage?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`usage ${r.status}`);
  return (await r.json()).items;
}

export async function listPricing(token: string): Promise<Pricing[]> {
  const r = await staffFetch("/admin/api/v1/cost/pricing", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`pricing ${r.status}`);
  return (await r.json()).items;
}

export async function upsertPricing(
  token: string,
  body: {
    model: string;
    input_price_per_1k_x10000: number;
    output_price_per_1k_x10000: number;
    currency: string;
  },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/cost/pricing", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`upsert pricing ${r.status}`);
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/CostRoute.tsx
import { useEffect, useState } from "react";

import {
  getUsage, listPricing, type Pricing, upsertPricing, type UsageItem,
} from "../../api/adminCost";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function UsageTable({ items }: { items: UsageItem[] }) {
  return (
    <Card>
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">模型</th>
            <th className="px-3 py-2 text-right font-normal">输入 token</th>
            <th className="px-3 py-2 text-right font-normal">输出 token</th>
            <th className="px-3 py-2 text-right font-normal">输入成本</th>
            <th className="px-3 py-2 text-right font-normal">输出成本</th>
            <th className="px-3 py-2 text-right font-normal">合计</th>
            <th className="px-3 py-2 text-left font-normal">币种</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr><td colSpan={7} className="px-3 py-4 text-center text-ink-tertiary">暂无数据</td></tr>
          )}
          {items.map((i) => (
            <tr key={i.model} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{i.model}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.input_tokens}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.output_tokens}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.input_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.output_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-right text-ink-primary">{i.total_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-ink-tertiary">{i.currency ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function PricingForm({ onSaved, onError }: {
  onSaved: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [model, setModel] = useState("claude-sonnet-4-6");
  const [inP, setInP] = useState(30000);
  const [outP, setOutP] = useState(150000);
  const [cur, setCur] = useState("USD");
  async function submit() {
    if (!token) return;
    try {
      await upsertPricing(token, {
        model,
        input_price_per_1k_x10000: Number(inP),
        output_price_per_1k_x10000: Number(outP),
        currency: cur,
      });
      onSaved();
    } catch (e) { onError(e instanceof Error ? e.message : "保存失败"); }
  }
  return (
    <Card className="mt-3">
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="model" value={model}
          onChange={(e) => setModel(e.target.value)} className="w-56" />
        <Input type="number" value={inP} aria-label="输入单价×10000/千token"
          onChange={(e) => setInP(Number(e.target.value))} className="w-32" />
        <Input type="number" value={outP} aria-label="输出单价×10000/千token"
          onChange={(e) => setOutP(Number(e.target.value))} className="w-32" />
        <Input value={cur} aria-label="币种" onChange={(e) => setCur(e.target.value)} className="w-20" />
        <Button size="md" onClick={submit}>保存单价</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        单价存"每 1000 token × 10000"避免浮点。例：sonnet 输入 $3.00/1k → 30000。
      </p>
    </Card>
  );
}

function PricingList({ rows }: { rows: Pricing[] }) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">模型</th>
            <th className="px-3 py-2 text-right font-normal">输入×10000</th>
            <th className="px-3 py-2 text-right font-normal">输出×10000</th>
            <th className="px-3 py-2 text-left font-normal">币种</th>
            <th className="px-3 py-2 text-left font-normal">更新时间</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.model} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{p.model}</td>
              <td className="px-3 py-2 text-right">{p.input_price_per_1k_x10000}</td>
              <td className="px-3 py-2 text-right">{p.output_price_per_1k_x10000}</td>
              <td className="px-3 py-2">{p.currency}</td>
              <td className="px-3 py-2 text-ink-tertiary">{p.updated_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function CostRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "manager" || role === "admin";
  const canEditPricing = role === "engineer" || role === "admin";
  const [items, setItems] = useState<UsageItem[]>([]);
  const [pricing, setPricing] = useState<Pricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([
      getUsage(token, { with_cost: true }),
      listPricing(token),
    ])
      .then(([u, p]) => { setItems(u); setPricing(p); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要管理权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="Token 成本大盘" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <UsageTable items={items} />
            {canEditPricing && (
              <PricingForm onSaved={() => { setNotice("已保存"); reload(); }} onError={setErr} />
            )}
            <PricingList rows={pricing} />
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `CostRoute`，StaffLayout 块内加 `<Route path="/admin/cost" element={<CostRoute />} />`。

- [ ] **Step 4: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminCost.ts src/routes/admin/CostRoute.tsx src/App.tsx`
Expected: typecheck pass；新增 3 文件 eslint 0 problems。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminCost.ts web/src/routes/admin/CostRoute.tsx web/src/App.tsx
git commit -m "feat(admin): Token 成本大盘前端页（usage + 单价编辑）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 6 — RBAC 基础矩阵（admin）

## Task 6.1: RBAC 矩阵前端页（只读 + 跳账号页改角色）

**Files:**
- Create: `web/src/routes/admin/RbacRoute.tsx`
- Modify: `web/src/App.tsx`

设计：完全前端的只读矩阵——后端**不**做新表（M2 RBAC 第一阶段就是这种"展示+跳转"）。横轴角色 = 6 个；纵轴功能模块 = 后台 10+ 个；单元格"✓/✗"表示该角色在该模块的可见性。数据来源 = 前端 hardcoded 的权限矩阵（与 StaffLayout.tsx 的 `roles` 字段保持一致；保险起见 RbacRoute 里**单独维护这份矩阵**，避免相互导入耦合）。每行"模块"标题做成链接，跳转到对应后台页；底部一个跳转按钮"管理账号角色 →"指向 `/admin/staff`。

- [ ] **Step 1: 页面组件**

```tsx
// web/src/routes/admin/RbacRoute.tsx
import { Link } from "react-router-dom";

import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

const ROLES = ["agent", "senior", "supervisor", "engineer", "manager", "admin"];

type ModuleRow = {
  path: string;
  label: string;
  roles: string[];  // 哪些角色可见这个后台模块
};

const MODULES: ModuleRow[] = [
  { path: "/admin/dashboard",   label: "数据大盘",      roles: ["supervisor", "manager", "admin"] },
  { path: "/admin/staff",       label: "客服账号",      roles: ["admin"] },
  { path: "/admin/performance", label: "客服绩效",      roles: ["supervisor", "admin"] },
  { path: "/admin/qa",          label: "会话质检",      roles: ["supervisor", "admin"] },
  { path: "/admin/sla",         label: "SLA 配置",      roles: ["supervisor", "admin"] },
  { path: "/admin/tools",       label: "工具策略",      roles: ["engineer", "admin"] },
  { path: "/admin/cost",        label: "成本大盘",      roles: ["engineer", "manager", "admin"] },
  { path: "/admin/audit",       label: "操作审计",      roles: ["engineer", "admin"] },
  { path: "/admin/prompts",     label: "Prompt 灰度",   roles: ["admin"] },
  { path: "/admin/rbac",        label: "角色权限",      roles: ["admin"] },
];

function RoleMatrix() {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">模块</th>
              {ROLES.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MODULES.map((m) => (
              <tr key={m.path} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">
                  <Link to={m.path} className="text-brand">{m.label}</Link>
                </td>
                {ROLES.map((r) => (
                  <td key={r} className="px-3 py-2 text-center">
                    {m.roles.includes(r) ? (
                      <span className="text-status-success">✓</span>
                    ) : (
                      <span className="text-ink-tertiary">·</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function RbacRoute() {
  const { role } = useStaffSession();
  if (role !== "admin") {
    return (
      <PageContainer width="wide">
        <PageHeader title="角色权限" />
        <Alert variant="error">需要管理员权限</Alert>
      </PageContainer>
    );
  }
  return (
    <PageContainer width="wide">
      <PageHeader title="角色权限（只读）" />
      <p className="mb-3 text-body3 text-ink-secondary">
        M2 阶段一：展示六角色在各模块的可见性。改角色请到
        <Link to="/admin/staff" className="ml-1 text-brand">客服账号</Link>
        页面操作。M3 将引入 role_permissions 表支持自定义。
      </p>
      <RoleMatrix />
    </PageContainer>
  );
}
```

- [ ] **Step 2: 注册路由**

`web/src/App.tsx`：import `RbacRoute`，StaffLayout 块内加 `<Route path="/admin/rbac" element={<RbacRoute />} />`。

- [ ] **Step 3: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/routes/admin/RbacRoute.tsx src/App.tsx`
Expected: typecheck pass；自己改/建的 2 文件 eslint 0 problems。

- [ ] **Step 4: Commit**

```bash
git add web/src/routes/admin/RbacRoute.tsx web/src/App.tsx
git commit -m "feat(admin): RBAC 基础矩阵前端页（只读 + 跳账号页改角色）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# 收尾回归

- [ ] **Step 1: 后端全套**

Run: `cd server && make test`
Expected: 全绿，覆盖率 ≥ 75%。若新模块拉低覆盖率，补 1-2 个边界测试（如 `admin_qa.list_reviews` 的多过滤条件分支、`admin_cost.usage_by_model` 的 with_cost 缺失 pricing 分支）。
注意：`make test` 同时运行 `ruff check` 和 `ruff format --check`——本里程碑新增/改动文件必须 0 warning；M1 时已存在的 59 个 pre-existing ruff warning（agent tools / 老测试）非本里程碑责任，但若 `make test` 因此整体失败，记录 pre-existing 计数并对比"本次新增/改 的文件"是否引入新 warning。

- [ ] **Step 2: 前端检查**

Run: `cd web && pnpm typecheck`
Expected: 仅原有的 staffFetch.ts → clearStaffToken 报错保持（pre-existing，M1 即存在）；本里程碑新增/改动文件无新 typecheck 错。
Run: `cd web && pnpm test:ci`
Expected: 仅原有的 ImageThumb test 失败保持（pre-existing）；本里程碑无新引入失败。

- [ ] **Step 3: 真实 Postgres 验证（按项目硬规则）**

```bash
docker compose up -d --build api
cd server && alembic upgrade head
```
Expected: `alembic upgrade head` 在 PG 无错；以下冒烟在 PG 返回 200/期望码：
- 建质检评分卡 + 提交质检
- C 端用 X-BU-ID 调 `/api/v1/conversations/{id}/agent-rating/eligibility` 与 POST
- `PUT /admin/api/v1/tool-policies` 写一行 → 客服代查该工具返回 403
- `PUT /admin/api/v1/cost/pricing` + `GET /admin/api/v1/cost/usage?with_cost=true` 看到 cost 字段

特别检查：Task 5.1 加 `model` 列后，UPSERT 在 PG 上 `ON CONFLICT(subject_id, user_type, date)` 的 DO UPDATE 是否能正确处理 `COALESCE(CAST(:model AS TEXT), daily_token_usage.model)`（M1 已记录类型歧义对策，这里再次确认 PG 真实库行为）。

- [ ] **Step 4: 跨端同步检查**

本计划改动主要在 web 后台 + server API。两个面要确认：
- Phase 2 Task 2.4 满意度采集 UI 挂载到 `web/src/routes/ChatRoute.tsx`（C 端 H5 内嵌 APP）。**APP 内的 webview 需冷启动**拉新 dist hash（CLAUDE.md §1.5）。运行 `cd web && pnpm build` 重新生成 dist，让用户 APP 内冷启动 webview 验证按钮显示。
- Phase 4 工具权限矩阵生效面是后端，前端无跨端契约变化。Phase 5 token 用量 model 维度的写入是后端内部，前端无契约变化。

- [ ] **Step 5: 单 head 与提交链**

```bash
cd server && python -m alembic heads          # 必须单 head（M2 加了 5 个迁移）
git log --oneline -30                          # 显示 M2 提交链
git status --short                             # 应仅原有 11 modified + 1 untracked
```

---

## M2 完成定义（DoD）

- 会话质检：评分卡可创建/启用/停用；可针对会话提交质检；可按会话/质检员筛选历史记录。
- 客服满意度：C/B 端用户能查 eligibility + 提交 1-5 星评分；后台可按客服筛选 + 看均分。
- 客服绩效详情：前后端可按 staff_id + 时间窗看 KPI + 满意度 + 质检均分；账号页可跳转。
- AI 工具权限矩阵：表为空时行为与 M1 完全一致；表里有覆盖时按 DB 决定；客服代查 API 已接入；API 写操作落审计；前端矩阵可改可存。
- Token 成本大盘：写入路径已携带 model；按 model 分组聚合 + 单价换算；前端可看 usage + 编辑单价。
- RBAC 基础矩阵：admin 可看六角色×十模块的可见性矩阵；改角色仍走账号页。
- 后端 `make test` 全绿、覆盖率 ≥75%；alembic 单 head；真实 PG 迁移通过；前端 typecheck 无新增错。

## 遗留说明（非 M2 范围，记录以免遗忘）

- `daily_token_usage` 主键未含 model：同一 subject 同日多模型时 model 列只反映"最近一次写入"。M3 拆 by-model 旁路表彻底解决。
- RBAC 的 role_permissions 表 + 可视化编辑（自定义权限位）留 M3。
- `_STAFF_TOOL_WHITELIST` 常量保留在 staff_conversations.py 作 fallback；M3 可删（届时 DB 已是 source of truth）。
- 满意度采集 UI 是用户主动触发（按钮）；M3 可加"会话刚结束时主动弹一次"——前提是 useChat.ts/chat.ts 整理完。
- AI 自动调用工具（runtime → dispatch）的白名单/脱敏决策**未**改读 tool_policies——只改了客服代查链路。AI 链路改造留 M3（需要兼顾 AI agent 性能：每次工具调用前 DB 查询不可接受，需用 invalidate_cache 机制）。


