# 管理后台 M3a 实施计划 — 坐席与组织管理

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M1/M2 管理后台基础上落地坐席与组织管理（spec §5.1）：分组与技能标签、客服在线状态、排班、会话路由规则。

**Architecture:** 沿用 M1/M2 已建立的分层：SQLAlchemy Core schema + 每域 persistence + FastAPI APIRouter(`Depends(require_roles)`) + React Route。本里程碑要在 `conversations` 表加 `target_group_id` 列让"路由规则"落地——客服列表按组过滤。另在 `staff` 表加 `group_id` 和 `skills` 列。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind / vitest。

---

## 关键约定（所有 Task 必须遵守，沿用 M1/M2）

1. 可选筛选 SQL：`(CAST(:p AS TEXT) IS NULL OR col = :p)`，不可写裸 `(:p IS NULL OR ...)`。
2. 时间列：`from ai_engine.persistence.schema import now_str`。
3. 新增表 / 改列：① 加进 `schema.py`；② 建独立 alembic 迁移；③ 跑 `tests/test_alembic_migrations.py` 双 case 通过 + 单 head。**绝不**修改既有迁移文件。
4. 后端测试：`temp_db_url`/`seeded_db` fixture + `ASGITransport(app=main_mod.app)` + `AsyncClient`，参照 `tests/test_admin_qa_api.py`。
5. 角色 gate：用 `require_roles(*roles)`（M1 已实现）。
6. 写操作审计：调 `admin_audit.log_admin_action(...)`（M1 已实现）。
7. 后端单测：`cd server && .venv/bin/python -m pytest tests/xxx.py -v`；ruff：`cd server && .venv/bin/ruff check src/<file> tests/<file>`；自己改/建的文件 0 warning。
8. 前端验证：`cd web && pnpm typecheck` + `npx eslint src/<file> ...`（用针对性 eslint，绕开全局 pre-existing warning）。`max-lines-per-function` ≤80；`PageContainer width="wide"`。
9. git discipline：在 `main` 分支工作（用户同意，沿用 M1/M2 模式）。工作树有 11 modified + 1 untracked 预存脏文件（M1/M2 后已确认），**绝不**用 `git add -A/.`；用 `git add <精确路径>`；commit 用 `git -C /Users/sunchenglin/codes/tevau-cs-engine ...`（避免子目录路径混乱）。如果 `server/uv.lock` 被某次测试副产物改脏，controller 在收尾步骤 `git checkout server/uv.lock` 还原；本 task 不要 stage。
10. commit message 中文 + 末尾 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`。

---

## M1/M2 已交付基线（M3a 直接复用）

- 角色：`agent / senior / engineer / admin / supervisor / manager`。
- 鉴权依赖：`require_roles(*roles)`。
- 审计：`persistence/admin_audit.py` 的 `log_admin_action / list_admin_actions`。
- 后台外壳：`web/src/components/StaffLayout.tsx` 用 `roles?: string[]` 结构。
- M2 已加菜单项：`/admin/qa`、`/admin/performance`、`/admin/tools`、`/admin/cost`、`/admin/rbac`。
- 前端 UI 组件：`web/src/components/ui/*`。
- 前端 API 客户端模式：`web/src/api/admin*.ts`（`staffFetch` + `authHeaders`）。

---

## 文件结构总览

**后端新增**：
- `server/src/ai_engine/persistence/admin_staff_groups.py` — 分组 CRUD + 客服分组/技能读写
- `server/src/ai_engine/persistence/staff_presence.py` — 在线状态心跳 + 后台查询
- `server/src/ai_engine/persistence/admin_shifts.py` — 排班 CRUD + 查询
- `server/src/ai_engine/persistence/routing_rules.py` — 路由规则 CRUD + 内存缓存 + 路由匹配函数
- `server/src/ai_engine/api/admin_staff_groups.py`
- `server/src/ai_engine/api/staff_presence.py`（含心跳端点 + 后台查询端点）
- `server/src/ai_engine/api/admin_shifts.py`
- `server/src/ai_engine/api/admin_routing_rules.py`
- 4 个独立 alembic 迁移（分组/在线/排班/路由）

**后端修改**：
- `server/src/ai_engine/persistence/schema.py` — 新增 4 张表 + `staff` 加 `group_id`/`skills` 列 + `conversations` 加 `target_group_id` 列
- `server/src/ai_engine/main.py` — include 4 个新 router
- `server/src/ai_engine/persistence/conversations.py` — `list_pending` 等查询加按 target_group_id 过滤参数（**先 grep 确认非脏**）
- `server/src/ai_engine/api/staff_conversations.py` — 列表查询接受可选 `my_group_only` 参数 + 按当前 staff 所在 group 过滤（**先 grep 确认非脏**）

**前端新增**：
- `web/src/api/adminStaffGroups.ts`、`staffPresence.ts`、`adminShifts.ts`、`adminRoutingRules.ts`
- `web/src/hooks/useStaffPresenceHeartbeat.ts` — 心跳定时器
- `web/src/routes/admin/StaffGroupsRoute.tsx`、`PresenceRoute.tsx`、`ShiftsRoute.tsx`、`RoutingRulesRoute.tsx`

**前端修改**：
- `web/src/components/StaffLayout.tsx` — 加 4 个 M3a 菜单项；挂心跳 hook
- `web/src/App.tsx` — 注册 4 个新路由
- `web/src/routes/admin/StaffAccountsRoute.tsx` — 每行加分组下拉 + 技能编辑

---

# Phase 0 — 菜单扩展（前置）

## Task 0.1: 后台菜单加 M3a 四项

**Files:**
- Modify: `web/src/components/StaffLayout.tsx`

- [ ] **Step 1: 改 NAV_ITEMS**

`web/src/components/StaffLayout.tsx`：
- import 区加新图标：`Users2`、`Activity`、`CalendarClock`、`Route`（lucide-react）。
- 在 NAV_ITEMS 末尾（"角色权限"行之后）追加 4 项：
```typescript
  // M3a 坐席组织
  { to: "/admin/staff-groups", label: "客服分组", short: "分组", icon: Users2, roles: ["supervisor", "admin"] },
  { to: "/admin/presence", label: "在线状态", short: "在线", icon: Activity, roles: ["supervisor", "admin"] },
  { to: "/admin/shifts", label: "排班", short: "排班", icon: CalendarClock, roles: ["supervisor", "admin"] },
  { to: "/admin/routing", label: "会话路由", short: "路由", icon: Route, roles: ["supervisor", "admin"] },
```

- [ ] **Step 2: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/components/StaffLayout.tsx`
Expected: 双 0 problems。

- [ ] **Step 3: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/components/StaffLayout.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 后台菜单加 M3a 四项（分组/在线/排班/路由）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 1 — 分组与技能标签

## Task 1.1: staff_groups 表 + staff 加 group_id/skills 列 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 改 schema.py**

在 `schema.py` 中：

(a) 找到 `staff` 表定义（M1 时在 70 行左右），在 `Column("active", ...)` 之后插入两列：
```python
    Column("group_id", Integer),  # 可选：所属客服组（M3a 新增）
    Column("skills", Text),  # 可选：技能标签 JSON 数组字符串 ["c","b","stock"]（M3a 新增）
```

(b) 在 `schema.py` 末尾追加：
```python
# 客服分组（M3a §5.1.b）
staff_groups = Table(
    "staff_groups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("description", Text),
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
)
Index("ux_staff_group_name", staff_groups.c.name, unique=True)
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "staff_groups_and_skills"`
编辑生成的文件：
```python
def upgrade() -> None:
    op.create_table(
        "staff_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("ux_staff_group_name", "staff_groups", ["name"], unique=True)
    # staff 加列（SQLite batch + PG 直接 ALTER）
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.add_column(sa.Column("group_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("skills", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_column("skills")
        batch_op.drop_column("group_id")
    op.drop_index("ux_staff_group_name", table_name="staff_groups")
    op.drop_table("staff_groups")
```
保留 alembic 自动生成的 revision/down_revision 头。

- [ ] **Step 3: 跑 parity + heads**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v`
Expected: 2 pass。
Run: `cd server && .venv/bin/python -m alembic heads` — 单 head 指向新 revision。

- [ ] **Step 4: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): staff_groups 表 + staff 加 group_id/skills 列 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```
提交前 `git status` 核确只有 schema.py + 新迁移在 stage。

---

## Task 1.2: 分组 persistence + staff skills/group 读写

**Files:**
- Create: `server/src/ai_engine/persistence/admin_staff_groups.py`
- Modify: `server/src/ai_engine/persistence/staff.py`（追加 `set_staff_group`、`set_staff_skills`、扩展 `list_staff` 返回字段）
- Test: `server/tests/test_admin_staff_groups_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_staff_groups_dao.py
import json

from ai_engine.persistence import admin_staff_groups, staff as staff_mod


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_group_crud(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("证券组", "处理证券类问题")
    rows = await admin_staff_groups.list_groups()
    assert len(rows) == 1 and rows[0]["id"] == gid
    assert rows[0]["name"] == "证券组"


async def test_group_name_unique(temp_db_url):
    await _init(temp_db_url)
    await admin_staff_groups.create_group("证券组", None)
    import pytest
    with pytest.raises(Exception):
        await admin_staff_groups.create_group("证券组", None)


async def test_set_staff_group_and_skills(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("证券组", None)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.set_staff_group("AG1", gid)
    await staff_mod.set_staff_skills("AG1", ["c", "stock"])
    rows = await staff_mod.list_staff()
    row = next(r for r in rows if r["staff_id"] == "AG1")
    assert int(row["group_id"]) == gid
    assert json.loads(row["skills"]) == ["c", "stock"]


async def test_set_staff_group_none_clears(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("g", None)
    await staff_mod.create_staff("AG1", "x", "agent", "x")
    await staff_mod.set_staff_group("AG1", gid)
    await staff_mod.set_staff_group("AG1", None)
    row = next(r for r in await staff_mod.list_staff() if r["staff_id"] == "AG1")
    assert row["group_id"] is None
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_staff_groups_dao.py -v`
Expected: ModuleNotFoundError admin_staff_groups。

- [ ] **Step 3: 实现 admin_staff_groups.py**

```python
# server/src/ai_engine/persistence/admin_staff_groups.py
"""客服分组 CRUD。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_group(name: str, description: str | None) -> int:
    return await db.insert_returning_id(
        "INSERT INTO staff_groups(name, description, created_at) "
        "VALUES (:n, :d, :now) RETURNING id",
        {"n": name, "d": description, "now": now_str()},
    )


async def list_groups(active_only: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT id, name, description, active, created_at FROM staff_groups"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    return await db.fetch_all(sql)


async def update_group(
    group_id: int, name: str | None = None, description: str | None = None
) -> None:
    await db.execute(
        "UPDATE staff_groups SET "
        "name = COALESCE(CAST(:n AS TEXT), name), "
        "description = COALESCE(CAST(:d AS TEXT), description) "
        "WHERE id = :id",
        {"n": name, "d": description, "id": int(group_id)},
    )


async def set_group_active(group_id: int, active: int) -> None:
    await db.execute(
        "UPDATE staff_groups SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(group_id)},
    )


async def delete_group(group_id: int) -> None:
    await db.execute("DELETE FROM staff_groups WHERE id = :id", {"id": int(group_id)})
```

- [ ] **Step 4: 扩展 staff.py**

读 `server/src/ai_engine/persistence/staff.py`。在文件末尾追加：
```python
import json as _json  # 命名避免与文件已有 import 冲突


async def set_staff_group(staff_id: str, group_id: int | None) -> None:
    await db.execute(
        "UPDATE staff SET group_id = :g WHERE staff_id = :sid",
        {"g": int(group_id) if group_id is not None else None, "sid": staff_id},
    )


async def set_staff_skills(staff_id: str, skills: list[str]) -> None:
    await db.execute(
        "UPDATE staff SET skills = :s WHERE staff_id = :sid",
        {"s": _json.dumps(skills, ensure_ascii=False), "sid": staff_id},
    )
```

修改既有 `list_staff`：把 SELECT 列表里加 `group_id, skills`：
找到 `list_staff` 函数（M1 时实现），把 SQL 改为：
```python
    return await db.fetch_all(
        "SELECT id, staff_id, display_name, role, active, group_id, skills, created_at "
        "FROM staff ORDER BY id"
    )
```

- [ ] **Step 5: 跑测试 PASS**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_staff_groups_dao.py -v` (4 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/admin_staff_groups.py src/ai_engine/persistence/staff.py tests/test_admin_staff_groups_dao.py`。

- [ ] **Step 6: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/admin_staff_groups.py server/src/ai_engine/persistence/staff.py server/tests/test_admin_staff_groups_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 分组 CRUD + staff group/skills 字段读写" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: 分组 API + 账号 PATCH 加 group/skills

**Files:**
- Create: `server/src/ai_engine/api/admin_staff_groups.py`
- Modify: `server/src/ai_engine/api/admin_staff.py`（扩展 `StaffPatchIn` + `patch_staff` 处理 group_id/skills）
- Modify: `server/src/ai_engine/main.py`（include router）
- Test: `server/tests/test_admin_staff_groups_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_staff_groups_api.py
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
    await create_staff("AD1", "管理员", "admin", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
        "admin": issue_staff_token("AD1", "admin"),
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
        r = await c.get("/admin/api/v1/staff-groups", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_group(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/staff-groups",
            json={"name": "证券组", "description": "证券"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/staff-groups", headers=_h(env["sup"]))).json()["groups"]
    assert any(g["name"] == "证券组" for g in listed)
    audits = await admin_audit.list_admin_actions(action="staff_group.create", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)


async def test_patch_staff_group_and_skills(env):
    async with await _c() as c:
        r0 = await c.post("/admin/api/v1/staff-groups",
                          json={"name": "g1", "description": None},
                          headers=_h(env["sup"]))
        gid = r0.json()["id"]
        r = await c.patch(
            "/admin/api/v1/staff/AG1",
            json={"group_id": gid, "skills": ["c", "stock"]},
            headers=_h(env["admin"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))).json()["staff"]
    ag1 = next(s for s in listed if s["staff_id"] == "AG1")
    assert int(ag1["group_id"]) == gid
    import json
    assert json.loads(ag1["skills"]) == ["c", "stock"]
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_staff_groups_api.py -v` → 404 / 字段缺失。

- [ ] **Step 3: 实现路由 admin_staff_groups.py**

```python
# server/src/ai_engine/api/admin_staff_groups.py
"""客服分组管理（supervisor/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_staff_groups

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/staff-groups")
async def list_groups(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"groups": await admin_staff_groups.list_groups()}


class GroupIn(BaseModel):
    name: str
    description: str | None = None


@router.post("/admin/api/v1/staff-groups")
async def create_group(body: GroupIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    gid = await admin_staff_groups.create_group(body.name, body.description)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="staff_group.create",
        target_type="staff_group", target_id=str(gid), detail={"name": body.name},
    )
    return {"ok": True, "id": gid}


class GroupPatchIn(BaseModel):
    name: str | None = None
    description: str | None = None
    active: int | None = None


@router.patch("/admin/api/v1/staff-groups/{group_id}")
async def patch_group(
    group_id: int, body: GroupPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    if body.name is not None or body.description is not None:
        await admin_staff_groups.update_group(group_id, body.name, body.description)
    if body.active is not None:
        await admin_staff_groups.set_group_active(group_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="staff_group.update",
        target_type="staff_group", target_id=str(group_id),
        detail=body.model_dump(exclude_none=True),
    )
    return {"ok": True}


@router.delete("/admin/api/v1/staff-groups/{group_id}")
async def delete_group(group_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await admin_staff_groups.delete_group(group_id)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="staff_group.delete",
        target_type="staff_group", target_id=str(group_id),
    )
    return {"ok": True}
```

- [ ] **Step 4: 扩展 admin_staff.py 的 PATCH**

读 `server/src/ai_engine/api/admin_staff.py`。在 `StaffPatchIn` 类加两个字段：
```python
class StaffPatchIn(BaseModel):
    display_name: str | None = None
    role: str | None = None
    active: int | None = None
    group_id: int | None = None
    skills: list[str] | None = None
```
在 `patch_staff` 函数中，`if body.active is not None: await staff_mod.set_staff_active(...)` 之后追加：
```python
    if body.group_id is not None:
        await staff_mod.set_staff_group(staff_id, body.group_id)
    if body.skills is not None:
        await staff_mod.set_staff_skills(staff_id, body.skills)
```
保留其它逻辑不动（含原有 ValueError→400 try/except 和审计调用——审计的 detail 会自动通过 `body.model_dump(exclude_none=True)` 包含新字段，无需改）。

注意：`body.group_id is not None` 也会把"清空分组"语义（前端传 0 或 -1 表示清空？）排除——这里语义为"不传则保留；传整数则设为该值"。前端如需清空，需扩展支持 `group_id == 0` 表示 null。M3a 先做最小语义，前端用专门"删除分组成员"端点（或后续 M3b 扩展）。

- [ ] **Step 5: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_staff_groups import router as admin_staff_groups_router` + `app.include_router(admin_staff_groups_router)`。

- [ ] **Step 6: 跑测试 PASS**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_staff_groups_api.py tests/test_admin_staff_api.py -v` (既有 admin_staff API 不退化)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_staff_groups.py src/ai_engine/api/admin_staff.py src/ai_engine/main.py tests/test_admin_staff_groups_api.py`。

- [ ] **Step 7: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_staff_groups.py server/src/ai_engine/api/admin_staff.py server/src/ai_engine/main.py server/tests/test_admin_staff_groups_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 分组 API + 账号 PATCH 加 group_id/skills" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.4: 分组管理前端 + 账号页加分组/技能编辑

**Files:**
- Create: `web/src/api/adminStaffGroups.ts`
- Create: `web/src/routes/admin/StaffGroupsRoute.tsx`
- Modify: `web/src/api/adminStaff.ts`（扩展类型 + patchStaff 支持 group_id/skills）
- Modify: `web/src/routes/admin/StaffAccountsRoute.tsx`（每行加分组下拉 + 技能 input）
- Modify: `web/src/App.tsx`（注册路由）

- [ ] **Step 1: 新建 adminStaffGroups.ts**

```typescript
// web/src/api/adminStaffGroups.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type StaffGroup = {
  id: number;
  name: string;
  description: string | null;
  active: number;
  created_at: string;
};

export async function listGroups(token: string): Promise<StaffGroup[]> {
  const r = await staffFetch("/admin/api/v1/staff-groups", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).groups;
}

export async function createGroup(
  token: string, body: { name: string; description?: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/staff-groups", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
}

export async function patchGroup(
  token: string, id: number,
  body: { name?: string; description?: string; active?: number },
): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff-groups/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function deleteGroup(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff-groups/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: 扩展 adminStaff.ts**

读 `web/src/api/adminStaff.ts`。修改 `StaffRow` 类型加两个字段：
```typescript
export type StaffRow = {
  id: number;
  staff_id: string;
  display_name: string;
  role: string;
  active: number;
  group_id: number | null;
  skills: string | null;  // JSON 字符串
  created_at: string;
};
```
修改 `patchStaff` 的 body 类型：
```typescript
export async function patchStaff(
  token: string,
  staffId: string,
  body: { display_name?: string; role?: string; active?: number; group_id?: number; skills?: string[] },
): Promise<void> {
  // 函数体不变
```
其他函数保留不动。

- [ ] **Step 3: 新建 StaffGroupsRoute**

```tsx
// web/src/routes/admin/StaffGroupsRoute.tsx
import { useEffect, useState } from "react";

import {
  createGroup, deleteGroup, listGroups, patchGroup, type StaffGroup,
} from "../../api/adminStaffGroups";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function GroupForm({ onCreated, onError }: { onCreated: () => void; onError: (m: string) => void }) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  async function submit() {
    if (!token || !name) return;
    try { await createGroup(token, { name, description: desc || undefined }); setName(""); setDesc(""); onCreated(); }
    catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="分组名" value={name} className="w-44"
          onChange={(e) => setName(e.target.value)} />
        <Input placeholder="描述（可选）" value={desc} className="w-60"
          onChange={(e) => setDesc(e.target.value)} />
        <Button size="md" onClick={submit} disabled={!name}>新建分组</Button>
      </div>
    </Card>
  );
}

function GroupRow({ g, onChanged, onError }: {
  g: StaffGroup; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function toggle() {
    if (!token) return;
    try { await patchGroup(token, g.id, { active: g.active ? 0 : 1 }); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function remove() {
    if (!token) return;
    try { await deleteGroup(token, g.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2 text-ink-primary">{g.id}</td>
      <td className="px-3 py-2 text-ink-primary">{g.name}</td>
      <td className="px-3 py-2 text-ink-secondary">{g.description ?? "—"}</td>
      <td className="px-3 py-2">{g.active ? "启用" : "停用"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={toggle}>{g.active ? "停用" : "启用"}</button>
          <button className="text-status-error" onClick={remove}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function StaffGroupsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGroups(token).then(setGroups).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服分组" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (<LoadingState />) : allowed && (
        <>
          <GroupForm onCreated={reload} onError={setErr} />
          <Card className="mt-3">
            <table className="w-full text-body3">
              <thead>
                <tr className="border-b border-line text-ink-secondary">
                  <th className="px-3 py-2 text-left font-normal">ID</th>
                  <th className="px-3 py-2 text-left font-normal">分组名</th>
                  <th className="px-3 py-2 text-left font-normal">描述</th>
                  <th className="px-3 py-2 text-left font-normal">状态</th>
                  <th className="px-3 py-2 text-left font-normal">操作</th>
                </tr>
              </thead>
              <tbody>
                {groups.length === 0 && (
                  <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">暂无分组</td></tr>
                )}
                {groups.map((g) => <GroupRow key={g.id} g={g} onChanged={reload} onError={setErr} />)}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 4: 改 StaffAccountsRoute 加分组下拉 + 技能 input**

读 `web/src/routes/admin/StaffAccountsRoute.tsx`，定位 `StaffTable` 子组件中渲染每行的代码块。

(a) 在文件顶部 import 加：
```typescript
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
```

(b) `StaffAccountsRoute` 主组件加 groups 状态：
- 在 `const [rows, setRows] = useState<StaffRow[]>([]);` 之后加 `const [groups, setGroups] = useState<StaffGroup[]>([]);`
- 在 `reload()` 函数里把 `listStaff(token)` 改为 `Promise.all([listStaff(token), listGroups(token)])`，then 解构两个数组分别 setRows / setGroups。

(c) `StaffTable` 组件签名加 `groups` prop，在每行的"角色"列之后插入一个"分组"列：
- header 加 `<th className="px-3 py-2 text-left font-normal">分组</th>`
- 数据行加：
```tsx
<td className="px-3 py-2">
  <select value={s.group_id ?? 0} className="rounded border border-line px-1 py-0.5"
    onChange={async (e) => {
      if (!token) return;
      const v = Number(e.target.value);
      try { await patchStaff(token, s.staff_id, { group_id: v }); onRefresh(); }
      catch (err) { onError(err instanceof Error ? err.message : "操作失败"); }
    }}>
    <option value={0}>—</option>
    {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
  </select>
</td>
```
（前端临时用 `0` 代表"无分组"——后端目前不支持 0→null，但本 M3a 不做"清空"，需要清空时按 spec 改后端用 0 表示 null。本 task 简化为：不支持点回"—"清空，只能切换到其它组。）

- [ ] **Step 5: 注册路由**

`web/src/App.tsx`：import `StaffGroupsRoute`，StaffLayout 块内加 `<Route path="/admin/staff-groups" element={<StaffGroupsRoute />} />`。

- [ ] **Step 6: 验证**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminStaffGroups.ts src/api/adminStaff.ts src/routes/admin/StaffGroupsRoute.tsx src/routes/admin/StaffAccountsRoute.tsx src/App.tsx`
Expected: typecheck pass；改/建 5 文件 eslint 0 problems。

- [ ] **Step 7: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminStaffGroups.ts web/src/api/adminStaff.ts web/src/routes/admin/StaffGroupsRoute.tsx web/src/routes/admin/StaffAccountsRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 分组管理前端页 + 账号页加分组下拉" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 2 — 客服在线状态

## Task 2.1: staff_presence 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

在 `schema.py` 末尾追加：
```python
# 客服在线状态（M3a §5.1.c）— 心跳更新 last_seen_at；后台按 5 分钟内有心跳算 online。
staff_presence = Table(
    "staff_presence",
    metadata,
    Column("staff_id", String(64), primary_key=True),
    Column("status", String(16), nullable=False, server_default="offline"),  # online/away/offline
    Column("last_seen_at", String(32), nullable=False),
)
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "staff_presence"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "staff_presence",
        sa.Column("staff_id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="offline"),
        sa.Column("last_seen_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("staff_presence")
```

- [ ] **Step 3: 跑 parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): staff_presence 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: staff_presence persistence

**Files:**
- Create: `server/src/ai_engine/persistence/staff_presence.py`
- Test: `server/tests/test_staff_presence_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_staff_presence_dao.py
from ai_engine.persistence import staff_presence


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_heartbeat_insert_and_update(temp_db_url):
    await _init(temp_db_url)
    await staff_presence.heartbeat("AG1", "online")
    rows = await staff_presence.list_all()
    assert len(rows) == 1
    assert rows[0]["staff_id"] == "AG1"
    assert rows[0]["status"] == "online"
    # 第二次 upsert：更新而不是插入
    await staff_presence.heartbeat("AG1", "away")
    rows2 = await staff_presence.list_all()
    assert len(rows2) == 1
    assert rows2[0]["status"] == "away"


async def test_set_offline(temp_db_url):
    await _init(temp_db_url)
    await staff_presence.heartbeat("AG1", "online")
    await staff_presence.set_offline("AG1")
    rows = await staff_presence.list_all()
    assert rows[0]["status"] == "offline"


async def test_list_active_with_window(temp_db_url):
    """超过窗口的心跳视为 offline。"""
    await _init(temp_db_url)
    from ai_engine.persistence import db
    # 注入一个 5 分钟前的 last_seen_at（手写时间避免 datetime mock）
    await db.execute(
        "INSERT INTO staff_presence(staff_id, status, last_seen_at) "
        "VALUES ('OLD1', 'online', '2000-01-01 00:00:00')"
    )
    await staff_presence.heartbeat("FRESH1", "online")
    active = await staff_presence.list_active(window_seconds=300)
    ids = {r["staff_id"] for r in active}
    assert "FRESH1" in ids
    assert "OLD1" not in ids
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_presence_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/staff_presence.py
"""客服在线状态：心跳 upsert + 后台查询。"""

from datetime import UTC, datetime, timedelta
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def heartbeat(staff_id: str, status: str = "online") -> None:
    """心跳：upsert (staff_id, status, last_seen_at=now)。"""
    await db.execute(
        "INSERT INTO staff_presence(staff_id, status, last_seen_at) "
        "VALUES (:sid, :s, :now) "
        "ON CONFLICT(staff_id) DO UPDATE SET "
        "status = excluded.status, last_seen_at = excluded.last_seen_at",
        {"sid": staff_id, "s": status, "now": now_str()},
    )


async def set_offline(staff_id: str) -> None:
    await db.execute(
        "UPDATE staff_presence SET status = 'offline' WHERE staff_id = :sid",
        {"sid": staff_id},
    )


async def list_all() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT staff_id, status, last_seen_at FROM staff_presence ORDER BY staff_id"
    )


async def list_active(window_seconds: int = 300) -> list[dict[str, Any]]:
    """返回当前 status != offline 且 last_seen_at 在窗口内的客服。"""
    cutoff = (datetime.now(UTC) - timedelta(seconds=window_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    return await db.fetch_all(
        "SELECT staff_id, status, last_seen_at FROM staff_presence "
        "WHERE status != 'offline' AND last_seen_at >= :cutoff ORDER BY staff_id",
        {"cutoff": cutoff},
    )
```

- [ ] **Step 4: 跑测试 PASS + ruff + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_presence_dao.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/staff_presence.py tests/test_staff_presence_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/staff_presence.py server/tests/test_staff_presence_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 在线状态 persistence（心跳 upsert + 窗口查询）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.3: 在线状态 API（心跳 + 后台查询）

**Files:**
- Create: `server/src/ai_engine/api/staff_presence.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_staff_presence_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_staff_presence_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("SUP1", "主管", "supervisor", "x")
    yield {
        "agent": issue_staff_token("AG1", "agent"),
        "sup": issue_staff_token("SUP1", "supervisor"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_heartbeat_self(env):
    async with await _c() as c:
        r = await c.post("/staff/api/v1/presence", json={"status": "online"},
                         headers=_h(env["agent"]))
    assert r.status_code == 200


async def test_admin_list_presence(env):
    async with await _c() as c:
        await c.post("/staff/api/v1/presence", json={"status": "online"},
                     headers=_h(env["agent"]))
        r = await c.get("/admin/api/v1/presence", headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert any(p["staff_id"] == "AG1" and p["status"] == "online" for p in body["all"])
    assert "active" in body


async def test_admin_list_forbidden_for_agent(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/presence", headers=_h(env["agent"]))
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_presence_api.py -v` → 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/staff_presence.py
"""客服在线状态：自心跳（任何已登录 staff）+ 后台查询（supervisor/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles, require_staff
from ai_engine.persistence import staff_presence

router = APIRouter()
_sup = require_roles("supervisor", "admin")


_VALID_STATUS = {"online", "away", "offline"}


class HeartbeatIn(BaseModel):
    status: str = "online"


@router.post("/staff/api/v1/presence")
async def heartbeat(
    body: HeartbeatIn, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    status = body.status if body.status in _VALID_STATUS else "online"
    staff_id = str(staff.get("sub", ""))
    if not staff_id:
        return {"ok": False}
    await staff_presence.heartbeat(staff_id, status)
    return {"ok": True}


@router.get("/admin/api/v1/presence")
async def admin_list(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    all_rows = await staff_presence.list_all()
    active = await staff_presence.list_active(window_seconds=300)
    return {"all": all_rows, "active": active}
```

- [ ] **Step 4: 注册 router**

`main.py`：import `from ai_engine.api.staff_presence import router as staff_presence_router` + `app.include_router(staff_presence_router)`。

- [ ] **Step 5: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_presence_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/staff_presence.py src/ai_engine/main.py tests/test_staff_presence_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/staff_presence.py server/src/ai_engine/main.py server/tests/test_staff_presence_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 在线状态 API（心跳 + 后台查询）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.4: 在线状态前端（心跳 hook + 后台页）

**Files:**
- Create: `web/src/api/staffPresence.ts`
- Create: `web/src/hooks/useStaffPresenceHeartbeat.ts`
- Create: `web/src/routes/admin/PresenceRoute.tsx`
- Modify: `web/src/components/StaffLayout.tsx`（挂心跳 hook 进 layout）
- Modify: `web/src/App.tsx`（注册路由）

- [ ] **Step 1: API client + hook**

```typescript
// web/src/api/staffPresence.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Presence = {
  staff_id: string;
  status: string;
  last_seen_at: string;
};

export async function sendHeartbeat(token: string, status: "online" | "away" = "online"): Promise<void> {
  const r = await staffFetch("/staff/api/v1/presence", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`heartbeat ${r.status}`);
}

export async function listPresence(token: string): Promise<{ all: Presence[]; active: Presence[] }> {
  const r = await staffFetch("/admin/api/v1/presence", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`presence ${r.status}`);
  return r.json();
}
```

```typescript
// web/src/hooks/useStaffPresenceHeartbeat.ts
import { useEffect } from "react";

import { sendHeartbeat } from "../api/staffPresence";

import { useStaffSession } from "./useStaffSession";

const INTERVAL_MS = 60_000;  // 1 分钟心跳一次（后端窗口 5 分钟）

/** 客服已登录时定时发送在线心跳；登出后停止。 */
export function useStaffPresenceHeartbeat(): void {
  const { token } = useStaffSession();
  useEffect(() => {
    if (!token) return;
    // 立刻先发一次，然后定时
    sendHeartbeat(token).catch(() => {});
    const id = window.setInterval(() => {
      sendHeartbeat(token).catch(() => {});
    }, INTERVAL_MS);
    return () => { window.clearInterval(id); };
  }, [token]);
}
```

- [ ] **Step 2: PresenceRoute**

```tsx
// web/src/routes/admin/PresenceRoute.tsx
import { useEffect, useState } from "react";

import { listPresence, type Presence } from "../../api/staffPresence";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function PresenceTable({ rows, title }: { rows: Presence[]; title: string }) {
  return (
    <>
      <div className="mt-3 text-body2 font-medium text-ink-primary">{title}（{rows.length}）</div>
      <Card className="mt-2">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">staff_id</th>
              <th className="px-3 py-2 text-left font-normal">状态</th>
              <th className="px-3 py-2 text-left font-normal">上次活跃</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={3} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
            )}
            {rows.map((p) => (
              <tr key={p.staff_id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{p.staff_id}</td>
                <td className="px-3 py-2">{p.status}</td>
                <td className="px-3 py-2 text-ink-tertiary">{p.last_seen_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

export function PresenceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [all, setAll] = useState<Presence[]>([]);
  const [active, setActive] = useState<Presence[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    listPresence(token)
      .then((d) => { setAll(d.all); setActive(d.active); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服在线状态" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? <LoadingState /> : allowed && (
        <>
          <PresenceTable rows={active} title="在线（5 分钟内有心跳）" />
          <PresenceTable rows={all} title="全部" />
        </>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 挂心跳 hook 进 StaffLayout**

读 `web/src/components/StaffLayout.tsx`。在文件顶部 import 加：
```typescript
import { useStaffPresenceHeartbeat } from "../hooks/useStaffPresenceHeartbeat";
```
在 `export function StaffLayout()` 函数体起始处（`const { token } = useStaffSession();` 之后）调用：
```typescript
  useStaffPresenceHeartbeat();
```
保留其它代码不动。

- [ ] **Step 4: 注册路由**

`web/src/App.tsx`：import `PresenceRoute` + StaffLayout 块内 `<Route path="/admin/presence" element={<PresenceRoute />} />`。

- [ ] **Step 5: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/api/staffPresence.ts src/hooks/useStaffPresenceHeartbeat.ts src/routes/admin/PresenceRoute.tsx src/components/StaffLayout.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/staffPresence.ts web/src/hooks/useStaffPresenceHeartbeat.ts web/src/routes/admin/PresenceRoute.tsx web/src/components/StaffLayout.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 在线状态心跳 hook + 后台展示页" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 3 — 排班

## Task 3.1: staff_shifts 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义 + 迁移**

`schema.py` 末尾追加：
```python
# 排班（M3a §5.1.c）
staff_shifts = Table(
    "staff_shifts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("staff_id", String(64), nullable=False),
    Column("start_at", String(32), nullable=False),  # "YYYY-MM-DD HH:MM:SS" UTC
    Column("end_at", String(32), nullable=False),
    Column("created_at", String(32), nullable=False),
)
Index("idx_shifts_staff_time", staff_shifts.c.staff_id, staff_shifts.c.start_at)
```

Run: `cd server && .venv/bin/python -m alembic revision -m "staff_shifts"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "staff_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("staff_id", sa.String(64), nullable=False),
        sa.Column("start_at", sa.String(32), nullable=False),
        sa.Column("end_at", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_shifts_staff_time", "staff_shifts", ["staff_id", "start_at"])


def downgrade() -> None:
    op.drop_index("idx_shifts_staff_time", table_name="staff_shifts")
    op.drop_table("staff_shifts")
```

- [ ] **Step 2: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): staff_shifts 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: 排班 persistence

**Files:**
- Create: `server/src/ai_engine/persistence/admin_shifts.py`
- Test: `server/tests/test_admin_shifts_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_shifts_dao.py
from ai_engine.persistence import admin_shifts


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_and_list(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    rows = await admin_shifts.list_shifts(staff_id="AG1")
    assert len(rows) == 1 and rows[0]["id"] == sid


async def test_filter_by_time_range(temp_db_url):
    await _init(temp_db_url)
    await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    await admin_shifts.create_shift("AG1", "2026-06-02 09:00:00", "2026-06-02 18:00:00")
    rows = await admin_shifts.list_shifts(
        staff_id="AG1", date_from="2026-06-02 00:00:00"
    )
    assert len(rows) == 1


async def test_delete_shift(temp_db_url):
    await _init(temp_db_url)
    sid = await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    await admin_shifts.delete_shift(sid)
    rows = await admin_shifts.list_shifts(staff_id="AG1")
    assert len(rows) == 0
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_shifts_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/admin_shifts.py
"""排班 CRUD + 按客服/时间范围查询。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_shift(staff_id: str, start_at: str, end_at: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO staff_shifts(staff_id, start_at, end_at, created_at) "
        "VALUES (:sid, :sa, :ea, :now) RETURNING id",
        {"sid": staff_id, "sa": start_at, "ea": end_at, "now": now_str()},
    )


async def list_shifts(
    staff_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, staff_id, start_at, end_at, created_at FROM staff_shifts "
        "WHERE (CAST(:sid AS TEXT) IS NULL OR staff_id = :sid) "
        "AND (CAST(:df AS TEXT) IS NULL OR start_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR end_at <= :dt) "
        "ORDER BY start_at LIMIT :lim",
        {"sid": staff_id, "df": date_from, "dt": date_to, "lim": limit},
    )


async def delete_shift(shift_id: int) -> None:
    await db.execute("DELETE FROM staff_shifts WHERE id = :id", {"id": int(shift_id)})
```

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_shifts_dao.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/admin_shifts.py tests/test_admin_shifts_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/admin_shifts.py server/tests/test_admin_shifts_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 排班 persistence（CRUD + 按客服/时间过滤）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: 排班 API

**Files:**
- Create: `server/src/ai_engine/api/admin_shifts.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_shifts_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_shifts_api.py
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
        r = await c.get("/admin/api/v1/shifts", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_delete_shift(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "AG1", "start_at": "2026-06-01 09:00:00",
                  "end_at": "2026-06-01 18:00:00"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        sid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/shifts?staff_id=AG1",
                              headers=_h(env["sup"]))).json()["shifts"]
        assert any(s["id"] == sid for s in listed)
        del_r = await c.delete(f"/admin/api/v1/shifts/{sid}", headers=_h(env["sup"]))
        assert del_r.status_code == 200
        listed_after = (await c.get("/admin/api/v1/shifts?staff_id=AG1",
                                    headers=_h(env["sup"]))).json()["shifts"]
        assert all(s["id"] != sid for s in listed_after)
    audits = await admin_audit.list_admin_actions(action="shift.create", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)
```

- [ ] **Step 2: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_shifts.py
"""排班管理（supervisor/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_shifts

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/shifts")
async def list_shifts(
    staff_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    staff: dict[str, Any] = Depends(_sup),
) -> dict[str, Any]:
    return {"shifts": await admin_shifts.list_shifts(
        staff_id=staff_id, date_from=date_from, date_to=date_to, limit=limit,
    )}


class ShiftIn(BaseModel):
    staff_id: str
    start_at: str
    end_at: str


@router.post("/admin/api/v1/shifts")
async def create_shift(body: ShiftIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    sid = await admin_shifts.create_shift(body.staff_id, body.start_at, body.end_at)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="shift.create",
        target_type="shift", target_id=str(sid), detail=body.model_dump(),
    )
    return {"ok": True, "id": sid}


@router.delete("/admin/api/v1/shifts/{shift_id}")
async def delete_shift(shift_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await admin_shifts.delete_shift(shift_id)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="shift.delete",
        target_type="shift", target_id=str(shift_id),
    )
    return {"ok": True}
```

`main.py`：import `from ai_engine.api.admin_shifts import router as admin_shifts_router` + `app.include_router(admin_shifts_router)`。

- [ ] **Step 3: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_shifts_api.py -v` (2 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_shifts.py src/ai_engine/main.py tests/test_admin_shifts_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_shifts.py server/src/ai_engine/main.py server/tests/test_admin_shifts_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 排班 API（create/list/delete + 审计）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.4: 排班前端页

**Files:**
- Create: `web/src/api/adminShifts.ts`
- Create: `web/src/routes/admin/ShiftsRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminShifts.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Shift = {
  id: number;
  staff_id: string;
  start_at: string;
  end_at: string;
  created_at: string;
};

export async function listShifts(
  token: string, opts?: { staff_id?: string; from?: string; to?: string },
): Promise<Shift[]> {
  const qs = new URLSearchParams();
  if (opts?.staff_id) qs.set("staff_id", opts.staff_id);
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(`/admin/api/v1/shifts?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).shifts;
}

export async function createShift(
  token: string, body: { staff_id: string; start_at: string; end_at: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/shifts", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
}

export async function deleteShift(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/shifts/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: ShiftsRoute**

```tsx
// web/src/routes/admin/ShiftsRoute.tsx
import { useEffect, useState } from "react";

import { createShift, deleteShift, listShifts, type Shift } from "../../api/adminShifts";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function ShiftForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [staffId, setStaffId] = useState("");
  const [start, setStart] = useState("2026-06-01 09:00:00");
  const [end, setEnd] = useState("2026-06-01 18:00:00");
  async function submit() {
    if (!token || !staffId) return;
    try { await createShift(token, { staff_id: staffId, start_at: start, end_at: end }); onCreated(); }
    catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="staff_id" value={staffId} className="w-32"
          onChange={(e) => setStaffId(e.target.value)} />
        <Input placeholder="start UTC" value={start} className="w-44"
          onChange={(e) => setStart(e.target.value)} />
        <Input placeholder="end UTC" value={end} className="w-44"
          onChange={(e) => setEnd(e.target.value)} />
        <Button size="md" onClick={submit} disabled={!staffId}>新建排班</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        时间格式："YYYY-MM-DD HH:MM:SS" UTC（与后端 now_str 一致）。
      </p>
    </Card>
  );
}

function ShiftRow({ s, onRemoved, onError }: {
  s: Shift; onRemoved: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function remove() {
    if (!token) return;
    try { await deleteShift(token, s.id); onRemoved(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{s.id}</td>
      <td className="px-3 py-2 text-ink-primary">{s.staff_id}</td>
      <td className="px-3 py-2 text-ink-secondary">{s.start_at}</td>
      <td className="px-3 py-2 text-ink-secondary">{s.end_at}</td>
      <td className="px-3 py-2">
        <button className="text-status-error" onClick={remove}>删除</button>
      </td>
    </tr>
  );
}

export function ShiftsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [filter, setFilter] = useState("");
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listShifts(token, filter ? { staff_id: filter } : undefined)
      .then(setShifts).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, filter]);

  return (
    <PageContainer width="wide">
      <PageHeader title="排班" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <>
          <ShiftForm onCreated={reload} onError={setErr} />
          <Card className="mt-3">
            <div className="flex items-end gap-2 px-page py-block-sm">
              <Input placeholder="按 staff_id 过滤" value={filter} className="w-44"
                onChange={(e) => setFilter(e.target.value)} />
            </div>
          </Card>
          {loading ? <LoadingState /> : (
            <Card className="mt-3">
              <table className="w-full text-body3">
                <thead>
                  <tr className="border-b border-line text-ink-secondary">
                    <th className="px-3 py-2 text-left font-normal">ID</th>
                    <th className="px-3 py-2 text-left font-normal">staff_id</th>
                    <th className="px-3 py-2 text-left font-normal">开始</th>
                    <th className="px-3 py-2 text-left font-normal">结束</th>
                    <th className="px-3 py-2 text-left font-normal">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {shifts.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
                  )}
                  {shifts.map((s) => <ShiftRow key={s.id} s={s} onRemoved={reload} onError={setErr} />)}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `ShiftsRoute` + `<Route path="/admin/shifts" element={<ShiftsRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminShifts.ts src/routes/admin/ShiftsRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminShifts.ts web/src/routes/admin/ShiftsRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 排班前端页（创建/列表/删除/按客服过滤）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 4 — 会话路由规则

## Task 4.1: routing_rules 表 + conversations 加 target_group_id + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: schema.py 改动**

(a) 找到 `conversations` 表定义（M1 时在 33 行左右），在已有最后一列（如 `Column("created_at", String(32), nullable=False),`）之前插入：
```python
    Column("target_group_id", Integer),  # M3a 路由规则匹配后落该会话的目标组；null 表示无定向
```

(b) `schema.py` 末尾追加：
```python
# 会话路由规则（M3a §5.1.d）
# 转人工或 needs_review 入队前匹配 active 规则，按 priority 升序取第一条命中，写 conversations.target_group_id。
routing_rules = Table(
    "routing_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("match_type", String(32), nullable=False),  # user_type / scope / keyword
    Column("match_value", String(256), nullable=False),  # user_type=c/b/g；keyword=text；scope=stock/security/etc
    Column("target_group_id", Integer, nullable=False),
    Column("priority", Integer, nullable=False, server_default="100"),  # 数字小先匹配
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "match_type IN ('user_type','scope','keyword')", name="ck_routing_match_type"
    ),
)
Index("idx_routing_priority", routing_rules.c.priority, routing_rules.c.active)
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "routing_rules_and_target_group"`
编辑生成文件：
```python
def upgrade() -> None:
    op.create_table(
        "routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_type", sa.String(32), nullable=False),
        sa.Column("match_value", sa.String(256), nullable=False),
        sa.Column("target_group_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "match_type IN ('user_type','scope','keyword')",
            name="ck_routing_match_type",
        ),
    )
    op.create_index("idx_routing_priority", "routing_rules", ["priority", "active"])
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("target_group_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_column("target_group_id")
    op.drop_index("idx_routing_priority", table_name="routing_rules")
    op.drop_table("routing_rules")
```

- [ ] **Step 3: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): routing_rules 表 + conversations.target_group_id 列 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.2: 路由规则 persistence + 路由匹配函数

**Files:**
- Create: `server/src/ai_engine/persistence/routing_rules.py`
- Test: `server/tests/test_routing_rules_dao.py`

匹配逻辑（`match_conversation_to_group`）：取当前 active 规则按 priority 升序遍历，第一条匹配的返回 target_group_id。匹配规则：
- `user_type` 类型：`match_value == conversation.user_type`
- `scope` 类型：把会话最近一条 user message content 当 hay；M3a 用 substring 简化匹配（包含 `match_value`）
- `keyword` 类型：同 scope 的 substring 匹配

简化：M3a 只在转人工触发点用这个函数；如果 conversation 没有 user message 内容（边界情况），scope/keyword 返回 None。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_routing_rules_dao.py
from ai_engine.persistence import routing_rules


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()


async def test_crud(temp_db_url):
    await _init(temp_db_url)
    rid = await routing_rules.create_rule("user_type", "c", 100, priority=10)
    rows = await routing_rules.list_rules()
    assert len(rows) == 1 and rows[0]["id"] == rid
    await routing_rules.set_active(rid, 0)
    assert int((await routing_rules.list_rules())[0]["active"]) == 0


async def test_match_by_user_type(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("user_type", "b", 7, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text=None
    )
    assert gid == 7


async def test_match_keyword(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("keyword", "卡片", 9, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="c", last_user_text="我想问卡片申请"
    )
    assert gid == 9


async def test_priority_first_wins(temp_db_url):
    await _init(temp_db_url)
    # 用 priority 10 命中 user_type=b → group 5；priority 5 命中 keyword=订单 → group 8
    await routing_rules.create_rule("user_type", "b", 5, priority=10)
    await routing_rules.create_rule("keyword", "订单", 8, priority=5)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text="订单问题"
    )
    assert gid == 8  # priority 5 < 10，先命中


async def test_no_match_returns_none(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("user_type", "c", 7, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text="xxx"
    )
    assert gid is None
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_routing_rules_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/routing_rules.py
"""会话路由规则 CRUD + 路由匹配。

匹配方式简化为：active 规则按 priority 升序遍历，第一条命中返回 target_group_id。
- user_type: 匹配 user_type == match_value
- scope/keyword: substring 匹配 last_user_text

模块级缓存：upsert/delete/set_active 后调 invalidate_cache。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_MATCH = {"user_type", "scope", "keyword"}
_CACHE: list[dict[str, Any]] | None = None


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _active_rules_sorted() -> list[dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT id, match_type, match_value, target_group_id, priority, active "
        "FROM routing_rules WHERE active = 1 ORDER BY priority ASC, id ASC"
    )
    _CACHE = rows
    return rows


async def create_rule(
    match_type: str, match_value: str, target_group_id: int, priority: int = 100
) -> int:
    if match_type not in _VALID_MATCH:
        raise ValueError(f"invalid match_type: {match_type}")
    rid = await db.insert_returning_id(
        "INSERT INTO routing_rules(match_type, match_value, target_group_id, priority, "
        "created_at) VALUES (:mt, :mv, :tg, :pr, :now) RETURNING id",
        {
            "mt": match_type,
            "mv": match_value,
            "tg": int(target_group_id),
            "pr": int(priority),
            "now": now_str(),
        },
    )
    invalidate_cache()
    return rid


async def list_rules() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, match_type, match_value, target_group_id, priority, active, created_at "
        "FROM routing_rules ORDER BY priority ASC, id ASC"
    )


async def set_active(rule_id: int, active: int) -> None:
    await db.execute(
        "UPDATE routing_rules SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(rule_id)},
    )
    invalidate_cache()


async def delete_rule(rule_id: int) -> None:
    await db.execute("DELETE FROM routing_rules WHERE id = :id", {"id": int(rule_id)})
    invalidate_cache()


async def match_for_conversation(
    user_type: str, last_user_text: str | None
) -> int | None:
    """返回首个命中规则的 target_group_id；无命中返回 None。"""
    for rule in await _active_rules_sorted():
        mt = str(rule["match_type"])
        mv = str(rule["match_value"])
        if mt == "user_type" and user_type == mv:
            return int(rule["target_group_id"])
        if mt in ("scope", "keyword") and last_user_text and mv in last_user_text:
            return int(rule["target_group_id"])
    return None
```

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_routing_rules_dao.py -v` (5 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/routing_rules.py tests/test_routing_rules_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/routing_rules.py server/tests/test_routing_rules_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 路由规则 persistence（CRUD + 路由匹配函数 + 缓存）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.3: 路由规则 API + 接入转人工

**Files:**
- Create: `server/src/ai_engine/api/admin_routing_rules.py`
- Modify: `server/src/ai_engine/main.py`
- Modify: `server/src/ai_engine/persistence/conversations.py`（先 grep 确认非脏）—— 加 `set_target_group` 函数
- Modify: 找到转人工/needs_review 入口（在 staff_conversations.py 或 chat.py），调用路由匹配 + 写 target_group_id
- Test: `server/tests/test_admin_routing_rules_api.py`

**接入点说明**：M1/M2 时转人工触发点在何处需 grep。可能在：
- `staff_conversations.py` 的某个端点（用户主动 escalate / 客服主动 release 时设 mode）
- `agent/runtime.py`（AI 决定转人工）

最稳的做法：本 task 提供一个 `route_conversation_now(conv_id)` 辅助函数（放 routing_rules persistence 模块或独立 service 文件），由现有调用方在 mode 变成 `human_pending` 时调用。如果 grep 没找到清晰单一入口，接入工作就是新加一处明显调用点（例如：在 `staff_conversations.py:235` 转派端点之后调用——但实际转派已知 staff，target_group 无意义）。

退而求其次：**M3a 不强行接入**，只完成 routing_rules CRUD + 匹配函数 + API + 前端，让 implementer 在 spec 内明确"接入点工作量超 M3a 范围，留 M3b 后续 task 接入"。本 task 末尾的 commit 说明此点。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_routing_rules_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import routing_rules
    from ai_engine.persistence.staff import create_staff

    routing_rules.invalidate_cache()
    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    routing_rules.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/routing-rules", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_set_active_delete(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/routing-rules",
            json={"match_type": "user_type", "match_value": "c",
                  "target_group_id": 1, "priority": 10},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/routing-rules",
                              headers=_h(env["sup"]))).json()["rules"]
        assert any(rr["id"] == rid for rr in listed)
        await c.patch(f"/admin/api/v1/routing-rules/{rid}",
                      json={"active": 0}, headers=_h(env["sup"]))
        await c.delete(f"/admin/api/v1/routing-rules/{rid}", headers=_h(env["sup"]))
        listed_after = (await c.get("/admin/api/v1/routing-rules",
                                    headers=_h(env["sup"]))).json()["rules"]
        assert all(rr["id"] != rid for rr in listed_after)
    audits = await admin_audit.list_admin_actions(action="routing_rule.create", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)


async def test_create_bad_match_type_400(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/routing-rules",
            json={"match_type": "bogus", "match_value": "x",
                  "target_group_id": 1, "priority": 10},
            headers=_h(env["sup"]),
        )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_routing_rules_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_routing_rules.py
"""会话路由规则（supervisor/admin）。写操作落审计 + 清缓存。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, routing_rules

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/routing-rules")
async def list_rules(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"rules": await routing_rules.list_rules()}


class RuleIn(BaseModel):
    match_type: str
    match_value: str
    target_group_id: int
    priority: int = 100


@router.post("/admin/api/v1/routing-rules")
async def create_rule(body: RuleIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    try:
        rid = await routing_rules.create_rule(
            body.match_type, body.match_value, body.target_group_id, body.priority,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="routing_rule.create",
        target_type="routing_rule", target_id=str(rid), detail=body.model_dump(),
    )
    return {"ok": True, "id": rid}


class RulePatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/routing-rules/{rule_id}")
async def patch_rule(
    rule_id: int, body: RulePatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await routing_rules.set_active(rule_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="routing_rule.update",
        target_type="routing_rule", target_id=str(rule_id), detail={"active": body.active},
    )
    return {"ok": True}


@router.delete("/admin/api/v1/routing-rules/{rule_id}")
async def delete_rule(
    rule_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await routing_rules.delete_rule(rule_id)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="routing_rule.delete",
        target_type="routing_rule", target_id=str(rule_id),
    )
    return {"ok": True}
```

`main.py`：import `from ai_engine.api.admin_routing_rules import router as admin_routing_rules_router` + `app.include_router(admin_routing_rules_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_routing_rules_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_routing_rules.py src/ai_engine/main.py tests/test_admin_routing_rules_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_routing_rules.py server/src/ai_engine/main.py server/tests/test_admin_routing_rules_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 路由规则 API（CRUD + 审计 + 缓存失效）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

注：本 task 完成 CRUD + 匹配函数；**真正接入"转人工时调用匹配 → 写 target_group_id"放 Task 4.5**（前端完成后），便于一起验证端到端。

---

## Task 4.4: 路由规则前端页

**Files:**
- Create: `web/src/api/adminRoutingRules.ts`
- Create: `web/src/routes/admin/RoutingRulesRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminRoutingRules.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type RoutingRule = {
  id: number;
  match_type: string;
  match_value: string;
  target_group_id: number;
  priority: number;
  active: number;
  created_at: string;
};

export async function listRules(token: string): Promise<RoutingRule[]> {
  const r = await staffFetch("/admin/api/v1/routing-rules", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).rules;
}

export async function createRule(
  token: string,
  body: { match_type: string; match_value: string; target_group_id: number; priority: number },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/routing-rules", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
}

export async function setRuleActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/routing-rules/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function deleteRule(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/routing-rules/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
```

- [ ] **Step 2: RoutingRulesRoute**

```tsx
// web/src/routes/admin/RoutingRulesRoute.tsx
import { useEffect, useState } from "react";

import {
  createRule, deleteRule, listRules, type RoutingRule, setRuleActive,
} from "../../api/adminRoutingRules";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function RuleForm({ groups, onCreated, onError }: {
  groups: StaffGroup[]; onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [mt, setMt] = useState("user_type");
  const [mv, setMv] = useState("");
  const [tg, setTg] = useState(groups[0]?.id ?? 0);
  const [pr, setPr] = useState(100);
  async function submit() {
    if (!token || !mv || !tg) return;
    try {
      await createRule(token, { match_type: mt, match_value: mv, target_group_id: tg, priority: pr });
      setMv("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <select value={mt} onChange={(e) => setMt(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          <option value="user_type">user_type</option>
          <option value="scope">scope</option>
          <option value="keyword">keyword</option>
        </select>
        <Input placeholder="匹配值（user_type=c/b/g；keyword=文本）" value={mv} className="w-60"
          onChange={(e) => setMv(e.target.value)} />
        <select value={tg} onChange={(e) => setTg(Number(e.target.value))}
          className="rounded border border-line px-2 py-1 text-body2">
          {groups.length === 0 ? <option value={0}>（先建分组）</option> : groups.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>
        <Input type="number" min={1} value={pr} aria-label="priority" className="w-24"
          onChange={(e) => setPr(Number(e.target.value))} />
        <Button size="md" onClick={submit} disabled={!mv || !tg}>新建规则</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        priority 越小越优先匹配。M3a 接入点是"转人工时"——见任务 4.5。
      </p>
    </Card>
  );
}

function RulesTable({ rules, groups, onChanged, onError }: {
  rules: RoutingRule[]; groups: StaffGroup[];
  onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const groupName = (id: number) => groups.find((g) => g.id === id)?.name ?? `#${id}`;
  async function toggle(r: RoutingRule) {
    if (!token) return;
    try { await setRuleActive(token, r.id, r.active ? 0 : 1); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function remove(r: RoutingRule) {
    if (!token) return;
    try { await deleteRule(token, r.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">优先级</th>
            <th className="px-3 py-2 text-left font-normal">类型</th>
            <th className="px-3 py-2 text-left font-normal">匹配值</th>
            <th className="px-3 py-2 text-left font-normal">目标组</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {rules.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">无规则</td></tr>
          )}
          {rules.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{r.priority}</td>
              <td className="px-3 py-2">{r.match_type}</td>
              <td className="px-3 py-2 text-ink-secondary">{r.match_value}</td>
              <td className="px-3 py-2 text-ink-secondary">{groupName(r.target_group_id)}</td>
              <td className="px-3 py-2">{r.active ? "启用" : "停用"}</td>
              <td className="px-3 py-2">
                <div className="flex gap-2">
                  <button className="text-brand" onClick={() => toggle(r)}>
                    {r.active ? "停用" : "启用"}
                  </button>
                  <button className="text-status-error" onClick={() => remove(r)}>删除</button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function RoutingRulesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listRules(token), listGroups(token)])
      .then(([rs, gs]) => { setRules(rs); setGroups(gs); })
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
      <PageHeader title="会话路由规则" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? <LoadingState /> : allowed && (
        <>
          <RuleForm groups={groups} onCreated={reload} onError={setErr} />
          <RulesTable rules={rules} groups={groups} onChanged={reload} onError={setErr} />
        </>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `RoutingRulesRoute` + `<Route path="/admin/routing" element={<RoutingRulesRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminRoutingRules.ts src/routes/admin/RoutingRulesRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminRoutingRules.ts web/src/routes/admin/RoutingRulesRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 路由规则前端页（CRUD + 目标分组下拉）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.5: 接入"转人工时调用路由匹配 → 写 target_group_id" + 客服列表按组过滤

**Files:**
- Modify: `server/src/ai_engine/persistence/conversations.py`（**先 grep 确认非脏**）—— 加 `set_target_group(conv_id, group_id)` + `list_pending` 加 `target_group_id` 可选过滤
- Modify: 转人工触发点（grep 定位）—— 设置 mode='human_pending' 时调用 routing_rules.match_for_conversation + conversations.set_target_group
- Modify: `server/src/ai_engine/api/staff_conversations.py`（先 grep 确认非脏）—— 列表查询接受 `my_group_only` query param；当 true 时按当前 staff 所在 group 过滤
- Test: `server/tests/test_routing_integration.py`

接入策略：
1. 加 persistence 工具 `conversations.set_target_group(conv_id, group_id)`：UPDATE conversations SET target_group_id = :g WHERE id = :id。
2. 加 helper `route_conversation_now(conv_id)`：读会话最近一条 user message text → 调 match → set_target_group。放在 routing_rules persistence 模块。
3. grep 转人工触发点："human_pending" 字符串 + ".mode = 'human_pending'" 模式。最可能在 chat.py 或 staff_conversations.py。如 chat.py 脏，从 chat.py 找到的入口标记为"延后接入"——退化方案：在 staff_conversations.py 的某个端点（如客服 release 会话回 AI、用户主动转人工等）调用。

退化方案承诺：如果转人工入口在脏文件 chat.py 中且必须改它，则**本 task 仅做 helper + 客服列表过滤**，转人工触发点接入延后到"chat.py 整理后"再做。本 task 提交时明确写在 commit message 里。

- [ ] **Step 1: 加 persistence helper**

读 `server/src/ai_engine/persistence/conversations.py` —— 它非脏（M1 时确认）。在文件末尾追加：
```python
async def set_target_group(conv_id: int, group_id: int | None) -> None:
    """M3a 路由匹配后调用，落 target_group_id 到会话。"""
    await db.execute(
        "UPDATE conversations SET target_group_id = :g WHERE id = :id",
        {"g": int(group_id) if group_id is not None else None, "id": int(conv_id)},
    )


async def last_user_text(conv_id: int) -> str | None:
    """取该会话最近一条 user 消息的 content（用于路由匹配）。"""
    row = await db.fetch_one(
        "SELECT content FROM messages WHERE conversation_id = :id AND role = 'user' "
        "ORDER BY id DESC LIMIT 1",
        {"id": int(conv_id)},
    )
    return str(row["content"]) if row else None
```

- [ ] **Step 2: 加 route_conversation_now helper**

读 `server/src/ai_engine/persistence/routing_rules.py`。在末尾追加：
```python
async def route_conversation_now(conv_id: int, user_type: str) -> int | None:
    """读会话最近 user 消息文本 → 匹配规则 → 写 target_group_id。返回匹配到的 group_id 或 None。

    幂等：可以重复调用；每次都会覆盖 target_group_id。
    """
    from ai_engine.persistence import conversations as conv_dao

    text = await conv_dao.last_user_text(conv_id)
    gid = await match_for_conversation(user_type=user_type, last_user_text=text)
    await conv_dao.set_target_group(conv_id, gid)
    return gid
```

- [ ] **Step 3: 在客服列表查询接入按组过滤**

读 `server/src/ai_engine/api/staff_conversations.py`（先确认非脏：`git status --short server/src/ai_engine/api/staff_conversations.py` 应无输出）。

定位列表端点：
```
grep -n "GET /staff/api/v1/conversations\|@router.get" server/src/ai_engine/api/staff_conversations.py | head
grep -n "def list_conversations\|target_group_id\|mode='human_pending'" server/src/ai_engine/api/staff_conversations.py | head
```
加可选 `my_group_only: bool = Query(default=False)` 到该端点签名。当 true 时：
1. 读当前 staff 的 group_id：
```python
from ai_engine.persistence.staff import get_staff  # 顶部已 import 过则跳过
staff_id = str(staff.get("sub", ""))
me = await get_staff(staff_id) if staff_id else None
my_group = int(me["group_id"]) if me and me.get("group_id") is not None else None
```
2. 在 SQL WHERE 加：
```python
"AND (target_group_id IS NULL OR target_group_id = :my_group)"
```
绑定 `:my_group = my_group`。`my_group is None` 时仍要传到 SQL（CAST 包裹）；可用本里程碑约定：
```python
"AND (CAST(:mg AS TEXT) IS NULL OR target_group_id IS NULL OR target_group_id = :mg)"
```
未启用 `my_group_only` 时不加该 WHERE 分支（保持兼容）。

最小化改动：仅在该列表端点加参数和过滤分支，不动其它端点；既有 `get_staff` 返回字段已被 M2 Task 3.3 复用（含 group_id 字段，本 M3a Task 1.2 又扩展），可直接读 `me["group_id"]`。

- [ ] **Step 4: 写集成测试**

```python
# server/tests/test_routing_integration.py
import pytest


async def test_route_conversation_writes_target_group(temp_db_url):
    """直接调 route_conversation_now：会话最近 user 消息匹配 keyword 规则 → 写 target_group_id。"""
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()
    # 准备会话 + 一条 user 消息（内容含"卡片"关键字）
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'c', 'u1', 'human_pending', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, status, created_at) "
        "VALUES (1, 'user', '我想问卡片的事', 'done', '2026-06-01 00:00:01')"
    )
    # 创建规则
    await routing_rules.create_rule("keyword", "卡片", target_group_id=7, priority=10)
    # 执行路由
    gid = await routing_rules.route_conversation_now(conv_id=1, user_type="c")
    assert gid == 7
    # 落库验证
    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = 1", {}
    )
    assert int(row["target_group_id"]) == 7


async def test_route_no_match_sets_null(temp_db_url):
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (2, 'b', 'BU1', 'human_pending', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, status, created_at) "
        "VALUES (2, 'user', '不相关的内容', 'done', '2026-06-01 00:00:01')"
    )
    # 规则只匹配 user_type=c（不匹配 b）
    await routing_rules.create_rule("user_type", "c", target_group_id=7, priority=10)
    gid = await routing_rules.route_conversation_now(conv_id=2, user_type="b")
    assert gid is None
    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = 2", {}
    )
    assert row["target_group_id"] is None
```

- [ ] **Step 5: 跑测试 + ruff + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_routing_integration.py tests/test_routing_rules_dao.py -v` (7 pass：5 既有 + 2 新)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/conversations.py src/ai_engine/persistence/routing_rules.py src/ai_engine/api/staff_conversations.py tests/test_routing_integration.py`

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/conversations.py server/src/ai_engine/persistence/routing_rules.py server/src/ai_engine/api/staff_conversations.py server/tests/test_routing_integration.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 路由匹配落 target_group_id + 客服列表按组过滤" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

如果接入"转人工时自动调用 route_conversation_now"的触发点在 chat.py（脏文件），本 task **不**强行改 chat.py；commit message 末尾追加："实际转人工入口（chat.py）暂未自动调用 route_conversation_now，运营需手动用 /admin/api/v1/routing-rules 提供的接口或由 M3b 等 chat.py 整理后接入。"

---

# 收尾回归

- [ ] **Step 1: 后端全套**

Run: `cd server && .venv/bin/pytest --cov=src/ai_engine --cov-report=term --cov-fail-under=75 2>&1 | tail -25`
Expected:
- 所有新增测试 pass
- 覆盖率 ≥ 75%
- 既有 pre-existing 失败保持（`test_user_upload_and_view` 1 个）

- [ ] **Step 2: 前端检查**

Run: `cd web && pnpm typecheck`
Expected: 仅 pre-existing staffFetch.ts 错保持。
Run: `cd web && pnpm test:ci`
Expected: 仅 pre-existing ImageThumb test 失败保持。

- [ ] **Step 3: alembic 单 head**

Run: `cd server && .venv/bin/python -m alembic heads`
Expected: 单 head（M3a 4 个迁移：staff_groups_and_skills, staff_presence, staff_shifts, routing_rules_and_target_group）。

- [ ] **Step 4: git status 核对**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short`
Expected: 仅 11 modified + 1 untracked（与会话开始/M2 完成时完全一致）。如果出现 `M server/uv.lock`：`git -C /Users/sunchenglin/codes/tevau-cs-engine checkout server/uv.lock` 还原。

- [ ] **Step 5: 提交链**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine log --oneline -25`

---

## M3a 完成定义（DoD）

- 分组与技能：分组可建/启停/删除；账号 PATCH 可设 group_id / skills；前端账号页有分组下拉。
- 在线状态：客服登录后定时心跳；后台可看在线列表 + 全部状态；5 分钟窗口判定 active。
- 排班：可建/列/删；按客服/时间过滤；写操作落审计。
- 路由规则：可建/启停/删；matching 函数命中按 priority 升序返回 target_group_id；route_conversation_now 落 conversations.target_group_id；客服列表可按 my_group_only 过滤。
- 后端 `make test` 全绿、覆盖率 ≥75%；alembic 单 head；新增 4 张表迁移通过 parity。

## 遗留说明（非 M3a 范围）

1. **转人工时自动调用 route_conversation_now**：如果触发点在 chat.py（用户脏文件），本 M3a 未强行接入。运营可通过 API 手动触发，或等 chat.py 整理后由后续 task 接入。
2. **PATCH staff group_id 清空语义**：M3a 前端用 `select value=0` 表示"无分组"，但后端 `body.group_id is not None` 不识别 0 为 null。若要支持清空，后端需扩展（如 `group_id=0` 转 `None`），或前端提供专门"清空分组成员"端点。M3b 视需要补。
3. **排班"在班验证"**：本 M3a 仅 CRUD，未在 listPresence 或 listPending 中加"当前在班"过滤。M3b 可加 `is_on_shift(staff_id, time)` 函数。
4. **心跳节流/批量**：当前每客服每分钟 1 次 POST；多 staff 同时在线时压力可控。如需进一步压低，可改成每 5 分钟一次心跳（窗口同步加大）。
