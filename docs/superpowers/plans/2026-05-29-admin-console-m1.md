# 管理后台 M1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 staff/admin 基础上，落地管理后台 M1（P0）：角色扩展+权限依赖、统一审计、客服账号 CRUD、工单详情页、SLA 配置与告警、核心指标大盘。

**Architecture:** 沿用现有分层——SQLAlchemy Core schema(`schema.py`) + 每域一个 persistence 模块(`db.fetch_*/execute/insert_returning_id`) + FastAPI APIRouter(`Depends(require_*)`) + React Route(`useStaffSession` + `components/ui/*` + `api/*.ts`)。新增表同步加 alembic 迁移（仓库有 parity 测试强制）。后端严格 TDD，前端给完整组件 + typecheck/lint + 手动验证。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async, sqlite+aiosqlite 测试 / postgresql+asyncpg 生产) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind / vitest。

---

## 关键约定（所有 Task 必须遵守）

1. **可选筛选 SQL** 一律用 `(CAST(:p AS TEXT) IS NULL OR col = :p)`，禁止裸 `(:p IS NULL OR ...)`（Postgres asyncpg 类型歧义，SQLite 测不出，生产 500）。
2. **时间列** 用 `from ai_engine.persistence.schema import now_str`，写 `"YYYY-MM-DD HH:MM:SS"` UTC 字符串。
3. **新增表** 必须：① 加进 `schema.py` 的 `metadata`；② 加一个 alembic 迁移（否则 `tests/test_alembic_migrations.py::test_alembic_upgrade_matches_init_db_schema` 失败）。
4. **后端测试** 用 `temp_db_url`/`seeded_db` fixture + `ASGITransport(app=main_mod.app)` + `AsyncClient`，参照 `tests/test_admin_prompts.py`。
5. **覆盖率门槛** `--cov-fail-under=75`，跑全套用 `cd server && make test`，跑单测用 `cd server && pytest tests/xxx.py -v`。
6. **提交粒度** 每个 Task 末尾一次 commit，message 用中文，结尾加 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`。
7. **改后端生效**：本地容器需 `docker compose up -d --build api`（restart 不够）；测试不依赖容器。

---

## 文件结构总览

后端新增：
- `server/src/ai_engine/persistence/admin_audit.py` — 后台操作审计：写入 + 查询（admin_audit_log 表）
- `server/src/ai_engine/persistence/admin_sla.py` — SLA 策略 CRUD + 违规计算
- `server/src/ai_engine/api/admin_staff.py` — 客服账号 CRUD 路由
- `server/src/ai_engine/api/admin_sla.py` — SLA 配置路由
- `server/src/ai_engine/api/admin_audit.py` — 审计中心查询路由
- `server/src/ai_engine/api/admin_dashboard.py` — 核心指标大盘路由
- `server/migrations/versions/<auto>_admin_console_m1.py` — 角色 CHECK 扩展 + admin_audit_log + sla_policies

后端修改：
- `server/src/ai_engine/persistence/schema.py` — staff CHECK 扩 6 角色；新增 admin_audit_log、sla_policies
- `server/src/ai_engine/persistence/staff.py` — `_VALID_ROLES` 扩展 + list/update/set_active/reset_password
- `server/src/ai_engine/auth/staff_session.py` — 新增 `require_roles(*roles)`
- `server/src/ai_engine/api/tickets.py` — 新增 `GET /staff/api/v1/tickets/{external_id}`
- `server/src/ai_engine/main.py` — include 4 个新 router

前端新增：
- `web/src/api/adminStaff.ts`、`adminSla.ts`、`adminAudit.ts`、`adminDashboard.ts` — API client
- `web/src/api/staff.ts` 内追加 `getTicketDetail`
- `web/src/routes/admin/StaffAccountsRoute.tsx`、`SlaRoute.tsx`、`AuditCenterRoute.tsx`、`DashboardRoute.tsx`
- `web/src/routes/staff/TicketDetailRoute.tsx`

前端修改：
- `web/src/components/StaffLayout.tsx` — `NAV_ITEMS` 由 `adminOnly:boolean` 改为 `roles?:string[]`，新增管理后台菜单项
- `web/src/App.tsx` — 注册新路由
- `web/src/routes/staff/TicketsRoute.tsx` — 列表行链接到详情

---

# Phase 0 — 前置基础设施

## Task 0.1: 角色体系扩展（supervisor / manager）

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py:79`（staff CheckConstraint）
- Modify: `server/src/ai_engine/persistence/staff.py:9`（`_VALID_ROLES`）
- Create: `server/migrations/versions/<auto>_admin_console_m1.py`（本 Task 仅写 staff CHECK 部分，0.3/3.1 再补表）
- Test: `server/tests/test_admin_roles.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_roles.py
from ai_engine.persistence.staff import create_staff, get_staff


async def test_create_supervisor_and_manager(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("MGR1", "老板", "manager", "x")
    assert (await get_staff("SUP1"))["role"] == "supervisor"
    assert (await get_staff("MGR1"))["role"] == "manager"


async def test_create_rejects_unknown_role(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    import pytest

    with pytest.raises(ValueError):
        await create_staff("X1", "x", "ceo", "x")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_roles.py -v`
Expected: FAIL — `create_staff` 现在 `_VALID_ROLES` 不含 supervisor/manager，抛 `ValueError("invalid role")`。

- [ ] **Step 3: 扩展应用层与 schema**

`server/src/ai_engine/persistence/staff.py:9` 改为：
```python
_VALID_ROLES = {"agent", "senior", "engineer", "admin", "supervisor", "manager"}
```

`server/src/ai_engine/persistence/schema.py:79` 的约束改为：
```python
    CheckConstraint(
        "role IN ('agent','senior','engineer','admin','supervisor','manager')",
        name="ck_staff_role",
    ),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_roles.py -v`
Expected: PASS（测试每次新建库走 `create_all`，新约束生效）。

- [ ] **Step 5: 生成迁移骨架并填入 staff CHECK 变更**

Run: `cd server && alembic revision -m "admin_console_m1"`
这会在 `migrations/versions/` 生成一个新文件（含正确的 `down_revision = 当前 head`）。编辑该文件，先填 staff CHECK（admin_audit_log、sla_policies 在 0.3/3.1 追加到同一文件的 upgrade/downgrade）：

```python
def upgrade() -> None:
    # staff: 角色 CHECK 扩展到 6 角色（batch 兼容 SQLite 重建 / PG 直接 ALTER）
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_constraint("ck_staff_role", type_="check")
        batch_op.create_check_constraint(
            "ck_staff_role",
            "role IN ('agent','senior','engineer','admin','supervisor','manager')",
        )


def downgrade() -> None:
    with op.batch_alter_table("staff", schema=None) as batch_op:
        batch_op.drop_constraint("ck_staff_role", type_="check")
        batch_op.create_check_constraint(
            "ck_staff_role", "role IN ('agent','senior','engineer','admin')"
        )
```

- [ ] **Step 6: 跑迁移 parity 测试**

Run: `cd server && pytest tests/test_alembic_migrations.py -v`
Expected: PASS（upgrade head 不报错，表集合匹配）。
注意：SQLite 对命名 CHECK 的反射有限，若 `drop_constraint` 在 SQLite batch 重建报"约束不存在"，改用 `batch_op.create_table_comment` 之外的回退——在 batch 上下文加 `recreate="always"`：`op.batch_alter_table("staff", recreate="always") as batch_op:` 并只调 `create_check_constraint`（重建时旧匿名约束不带入）。**生产 Postgres 必须单独验证**（见项目 SQLite/PG 差异约束）。

- [ ] **Step 7: Commit**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine
git add server/src/ai_engine/persistence/staff.py server/src/ai_engine/persistence/schema.py server/tests/test_admin_roles.py server/migrations/versions/
git commit -m "feat(admin): 角色体系扩展 supervisor/manager

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 0.2: `require_roles` 权限依赖

**Files:**
- Modify: `server/src/ai_engine/auth/staff_session.py`（追加函数）
- Test: `server/tests/test_require_roles.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_require_roles.py
import pytest
from fastapi import HTTPException

from ai_engine.auth.staff_session import require_roles


def test_allows_listed_role():
    dep = require_roles("supervisor", "admin")
    assert dep({"role": "admin"}) == {"role": "admin"}
    assert dep({"role": "supervisor"})["role"] == "supervisor"


def test_rejects_other_role():
    dep = require_roles("admin")
    with pytest.raises(HTTPException) as e:
        dep({"role": "agent"})
    assert e.value.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_require_roles.py -v`
Expected: FAIL — `ImportError: cannot import name 'require_roles'`。

- [ ] **Step 3: 实现 `require_roles`**

先在 `server/src/ai_engine/auth/staff_session.py` **顶部** import 区调整（ruff 要求 import 在模块顶部，放函数体内会 lint 失败）：
- 把 `from fastapi import Header, HTTPException` 改为 `from fastapi import Depends, Header, HTTPException`；
- 新增一行 `from collections.abc import Callable`（放到 `import time` 上方，stdlib 分组）。

然后在文件**末尾追加**函数：
```python
def require_roles(*roles: str) -> Callable[..., dict[str, Any]]:
    """生成一个 FastAPI 依赖：要求 staff.role ∈ roles，否则 403。

    用法：staff: dict = Depends(require_roles("supervisor", "admin"))
    入参 staff 由 require_staff 注入（验签 JWT）。直接传 dict 也可（便于单测）。
    """
    allowed = set(roles)

    def _dep(staff: dict[str, Any] = Depends(require_staff)) -> dict[str, Any]:
        if staff.get("role") not in allowed:
            raise HTTPException(403, "forbidden")
        return staff

    return _dep
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd server && pytest tests/test_require_roles.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/auth/staff_session.py server/tests/test_require_roles.py
git commit -m "feat(admin): 新增 require_roles 多角色权限依赖

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 0.3: 后台操作审计（admin_audit_log 表 + helper）

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`（新增 admin_audit_log）
- Create: `server/src/ai_engine/persistence/admin_audit.py`
- Modify: `server/migrations/versions/<auto>_admin_console_m1.py`（追加建表）
- Test: `server/tests/test_admin_audit.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_audit.py
from ai_engine.persistence import admin_audit


async def test_log_and_list(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await admin_audit.log_admin_action(
        actor="AD1", action="staff.create", target_type="staff",
        target_id="AG9", detail={"role": "agent"},
    )
    rows = await admin_audit.list_admin_actions(limit=10)
    assert len(rows) == 1
    assert rows[0]["actor"] == "AD1"
    assert rows[0]["action"] == "staff.create"
    assert rows[0]["target_id"] == "AG9"


async def test_list_filters_by_action(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await admin_audit.log_admin_action(actor="AD1", action="staff.create")
    await admin_audit.log_admin_action(actor="AD1", action="sla.update")
    rows = await admin_audit.list_admin_actions(action="sla.update", limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "sla.update"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: ai_engine.persistence.admin_audit`。

- [ ] **Step 3: 加表定义**

在 `server/src/ai_engine/persistence/schema.py` 末尾追加：
```python
# 后台统一操作审计：所有 admin/管理后台写操作落此表（账号/SLA/工具策略...）。
admin_audit_log = Table(
    "admin_audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor", String(128), nullable=False),
    Column("action", String(64), nullable=False),
    Column("target_type", String(64)),
    Column("target_id", String(128)),
    Column("detail_json", Text),
    Column("created_at", String(32), nullable=False),
)
Index("idx_admin_audit_created", admin_audit_log.c.created_at)
```

- [ ] **Step 4: 实现 helper**

```python
# server/src/ai_engine/persistence/admin_audit.py
"""后台统一操作审计：写入 + 查询。所有管理后台写操作调 log_admin_action 落痕。"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def log_admin_action(
    actor: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO admin_audit_log(actor, action, target_type, target_id, detail_json, created_at) "
        "VALUES (:actor, :action, :tt, :tid, :detail, :now) RETURNING id",
        {
            "actor": actor,
            "action": action,
            "tt": target_type,
            "tid": target_id,
            "detail": json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            "now": now_str(),
        },
    )


async def list_admin_actions(
    actor: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    # 可选筛选用 CAST(:p AS TEXT) 包裹，规避 Postgres 类型歧义
    return await db.fetch_all(
        "SELECT id, actor, action, target_type, target_id, detail_json, created_at "
        "FROM admin_audit_log "
        "WHERE (CAST(:actor AS TEXT) IS NULL OR actor = :actor) "
        "AND (CAST(:action AS TEXT) IS NULL OR action = :action) "
        "AND (CAST(:tt AS TEXT) IS NULL OR target_type = :tt) "
        "AND (CAST(:df AS TEXT) IS NULL OR created_at >= :df) "
        "AND (CAST(:dt AS TEXT) IS NULL OR created_at <= :dt) "
        "ORDER BY id DESC LIMIT :lim OFFSET :off",
        {
            "actor": actor,
            "action": action,
            "tt": target_type,
            "df": date_from,
            "dt": date_to,
            "lim": limit,
            "off": offset,
        },
    )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_audit.py -v`
Expected: PASS。

- [ ] **Step 6: 迁移追加建表**

编辑 0.1 生成的迁移文件，在 `upgrade()` 末尾追加、`downgrade()` 开头追加：
```python
    # upgrade() 内追加：
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_admin_audit_created", "admin_audit_log", ["created_at"])
```
```python
    # downgrade() 内（在 staff CHECK 还原之前）追加：
    op.drop_index("idx_admin_audit_created", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
```

- [ ] **Step 7: 跑迁移 parity 测试 + commit**

Run: `cd server && pytest tests/test_alembic_migrations.py tests/test_admin_audit.py -v`
Expected: PASS。
```bash
git add server/src/ai_engine/persistence/schema.py server/src/ai_engine/persistence/admin_audit.py server/tests/test_admin_audit.py server/migrations/versions/
git commit -m "feat(admin): admin_audit_log 表与统一审计 helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 0.4: 前端后台外壳（菜单支持多角色）

**Files:**
- Modify: `web/src/components/StaffLayout.tsx`（NAV_ITEMS 改 roles 数组 + 新菜单项占位）
- Test: 手动（typecheck + lint）

- [ ] **Step 1: 改 NavItem 类型与过滤逻辑**

`web/src/components/StaffLayout.tsx`：
- import 增加图标：`Users`, `Timer`, `ScrollText`, `LayoutDashboard`（lucide-react）。
- `NavItem` 类型把 `adminOnly?: boolean` 替换为 `roles?: string[]`（缺省=所有登录角色可见）。
- `useNavItems` 改为：
```typescript
function useNavItems() {
  const { role } = useStaffSession();
  return NAV_ITEMS.filter((i) => !i.roles || (role != null && i.roles.includes(role)));
}
```
- `NAV_ITEMS` 改为（原 Prompt 灰度项 `adminOnly:true` → `roles:["admin"]`，并加管理后台分组）：
```typescript
const NAV_ITEMS: NavItem[] = [
  { to: "/staff/conversations", label: "工作台", short: "工作台", icon: Inbox },
  { to: "/staff/tickets", label: "工单", icon: Ticket },
  { to: "/staff/kpi", label: "KPI", icon: BarChart3 },
  { to: "/staff/insights", label: "知识缺口", short: "缺口", icon: Lightbulb },
  { to: "/staff/audits", label: "工具审计", short: "审计", icon: ShieldCheck },
  // 管理后台（按角色显示）
  { to: "/admin/dashboard", label: "数据大盘", short: "大盘", icon: LayoutDashboard, roles: ["supervisor", "manager", "admin"] },
  { to: "/admin/staff", label: "客服账号", short: "账号", icon: Users, roles: ["admin"] },
  { to: "/admin/sla", label: "SLA", icon: Timer, roles: ["supervisor", "admin"] },
  { to: "/admin/audit", label: "操作审计", short: "操作", icon: ScrollText, roles: ["engineer", "admin"] },
  // Prompt 灰度后端鉴权仍是 require_admin(admin only)，故菜单 roles 保持 ["admin"]，
  // 与后端一致避免 engineer 点进去 403（统一到 engineer/admin 留 M2，见遗留说明）。
  { to: "/admin/prompts", label: "Prompt 灰度", short: "灰度", icon: SlidersHorizontal, roles: ["admin"] },
];
```

- [ ] **Step 2: typecheck + lint**

Run: `cd web && pnpm typecheck && pnpm lint`
Expected: 通过（此时新路由 `/admin/*` 尚未注册，菜单点击会 404，后续 Task 注册后修复——本步只验证组件本身编译/规范）。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/StaffLayout.tsx
git commit -m "feat(admin): 后台侧栏菜单支持多角色 + 管理后台分组占位

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 1 — 客服账号 CRUD（admin）

## Task 1.1: persistence 扩展

**Files:**
- Modify: `server/src/ai_engine/persistence/staff.py`（追加函数）
- Test: `server/tests/test_admin_staff_dao.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_staff_dao.py
from ai_engine.persistence import staff as staff_mod


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_list_staff(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.create_staff("AD1", "管理员", "admin", "x")
    rows = await staff_mod.list_staff()
    ids = {r["staff_id"] for r in rows}
    assert ids == {"AG1", "AD1"}
    assert all("password_hash" not in r for r in rows)  # 不泄露密码


async def test_update_staff_role_and_name(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.update_staff("AG1", display_name="高级客服", role="senior")
    row = await staff_mod.get_staff("AG1")
    assert row["display_name"] == "高级客服"
    assert row["role"] == "senior"


async def test_update_staff_partial_keeps_other(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.update_staff("AG1", role="supervisor")  # 只改角色
    row = await staff_mod.get_staff("AG1")
    assert row["display_name"] == "客服一"  # 名字保留
    assert row["role"] == "supervisor"


async def test_set_active_and_reset_password(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "oldpw")
    await staff_mod.set_staff_active("AG1", 0)
    assert int((await staff_mod.get_staff("AG1"))["active"]) == 0
    await staff_mod.reset_staff_password("AG1", "newpw")
    # 停用账号 authenticate 返回 None；先启用再验证新密码
    await staff_mod.set_staff_active("AG1", 1)
    assert await staff_mod.authenticate("AG1", "newpw") is not None
    assert await staff_mod.authenticate("AG1", "oldpw") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_staff_dao.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'list_staff'`。

- [ ] **Step 3: 实现 persistence 函数**

在 `server/src/ai_engine/persistence/staff.py` 末尾追加：
```python
async def list_staff() -> list[dict[str, Any]]:
    """账号列表（不含 password_hash）。"""
    return await db.fetch_all(
        "SELECT id, staff_id, display_name, role, active, created_at "
        "FROM staff ORDER BY id"
    )


async def update_staff(
    staff_id: str, display_name: str | None = None, role: str | None = None
) -> None:
    """部分更新 display_name / role（传 None 的字段保留原值）。"""
    if role is not None and role not in _VALID_ROLES:
        raise ValueError("invalid role")
    await db.execute(
        "UPDATE staff SET "
        "display_name = COALESCE(CAST(:name AS TEXT), display_name), "
        "role = COALESCE(CAST(:role AS TEXT), role) "
        "WHERE staff_id = :sid",
        {"name": display_name, "role": role, "sid": staff_id},
    )


async def set_staff_active(staff_id: str, active: int) -> None:
    await db.execute(
        "UPDATE staff SET active = :a WHERE staff_id = :sid",
        {"a": int(active), "sid": staff_id},
    )


async def reset_staff_password(staff_id: str, new_password: str) -> None:
    await db.execute(
        "UPDATE staff SET password_hash = :pw WHERE staff_id = :sid",
        {"pw": hash_password(new_password), "sid": staff_id},
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_staff_dao.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/staff.py server/tests/test_admin_staff_dao.py
git commit -m "feat(admin): staff persistence 增 list/update/set_active/reset_password

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.2: 账号 CRUD API

**Files:**
- Create: `server/src/ai_engine/api/admin_staff.py`
- Modify: `server/src/ai_engine/main.py`（include router）
- Test: `server/tests/test_admin_staff_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_staff_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AD1", "管理员", "admin", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {"admin": issue_staff_token("AD1", "admin"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _client():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_list_requires_admin(env):
    async with await _client() as c:
        assert (await c.get("/admin/api/v1/staff", headers=_h(env["agent"]))).status_code == 403
        r = await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))
    assert r.status_code == 200
    assert any(s["staff_id"] == "AD1" for s in r.json()["staff"])


async def test_create_staff(env):
    async with await _client() as c:
        r = await c.post(
            "/admin/api/v1/staff",
            json={"staff_id": "SUP1", "display_name": "主管", "role": "supervisor", "password": "pw"},
            headers=_h(env["admin"]),
        )
    assert r.status_code == 200
    async with await _client() as c:
        listed = (await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))).json()["staff"]
    assert any(s["staff_id"] == "SUP1" and s["role"] == "supervisor" for s in listed)


async def test_create_rejects_bad_role(env):
    async with await _client() as c:
        r = await c.post(
            "/admin/api/v1/staff",
            json={"staff_id": "X", "display_name": "x", "role": "ceo", "password": "pw"},
            headers=_h(env["admin"]),
        )
    assert r.status_code == 400


async def test_patch_and_reset(env):
    async with await _client() as c:
        await c.patch("/admin/api/v1/staff/AG1", json={"role": "senior"}, headers=_h(env["admin"]))
        await c.post("/admin/api/v1/staff/AG1/reset-password", json={"password": "np"}, headers=_h(env["admin"]))
        listed = (await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))).json()["staff"]
    assert next(s for s in listed if s["staff_id"] == "AG1")["role"] == "senior"


async def test_create_writes_audit(env):
    from ai_engine.persistence import admin_audit
    async with await _client() as c:
        await c.post(
            "/admin/api/v1/staff",
            json={"staff_id": "AG9", "display_name": "x", "role": "agent", "password": "pw"},
            headers=_h(env["admin"]),
        )
    rows = await admin_audit.list_admin_actions(action="staff.create", limit=10)
    assert any(r["target_id"] == "AG9" and r["actor"] == "AD1" for r in rows)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_staff_api.py -v`
Expected: FAIL — 404（路由未注册）。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_staff.py
"""客服账号管理（admin only）。所有写操作落 admin_audit_log。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit
from ai_engine.persistence import staff as staff_mod

router = APIRouter()
_admin = require_roles("admin")


@router.get("/admin/api/v1/staff")
async def list_staff(admin: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    return {"staff": await staff_mod.list_staff()}


class StaffCreateIn(BaseModel):
    staff_id: str
    display_name: str
    role: str
    password: str


@router.post("/admin/api/v1/staff")
async def create_staff(body: StaffCreateIn, admin: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    try:
        new_id = await staff_mod.create_staff(
            body.staff_id, body.display_name, body.role, body.password
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=admin.get("sub", "unknown"), action="staff.create",
        target_type="staff", target_id=body.staff_id, detail={"role": body.role},
    )
    return {"ok": True, "id": new_id}


class StaffPatchIn(BaseModel):
    display_name: str | None = None
    role: str | None = None
    active: int | None = None


@router.patch("/admin/api/v1/staff/{staff_id}")
async def patch_staff(
    staff_id: str, body: StaffPatchIn, admin: dict[str, Any] = Depends(_admin)
) -> dict[str, Any]:
    try:
        if body.display_name is not None or body.role is not None:
            await staff_mod.update_staff(staff_id, display_name=body.display_name, role=body.role)
        if body.active is not None:
            await staff_mod.set_staff_active(staff_id, body.active)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=admin.get("sub", "unknown"), action="staff.update",
        target_type="staff", target_id=staff_id,
        detail=body.model_dump(exclude_none=True),
    )
    return {"ok": True}


class ResetPwIn(BaseModel):
    password: str


@router.post("/admin/api/v1/staff/{staff_id}/reset-password")
async def reset_password(
    staff_id: str, body: ResetPwIn, admin: dict[str, Any] = Depends(_admin)
) -> dict[str, Any]:
    await staff_mod.reset_staff_password(staff_id, body.password)
    await admin_audit.log_admin_action(
        actor=admin.get("sub", "unknown"), action="staff.reset_password",
        target_type="staff", target_id=staff_id,
    )
    return {"ok": True}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import 区加 `from ai_engine.api.admin_staff import router as admin_staff_router`，并在 `app.include_router(admin_prompts_router)` 附近加 `app.include_router(admin_staff_router)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_staff_api.py -v`
Expected: PASS（5 个测试全过）。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_staff.py server/src/ai_engine/main.py server/tests/test_admin_staff_api.py
git commit -m "feat(admin): 客服账号 CRUD API（admin 鉴权 + 审计）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: 账号管理前端页

**Files:**
- Create: `web/src/api/adminStaff.ts`
- Create: `web/src/routes/admin/StaffAccountsRoute.tsx`
- Modify: `web/src/App.tsx`（注册路由）

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminStaff.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type StaffRow = {
  id: number;
  staff_id: string;
  display_name: string;
  role: string;
  active: number;
  created_at: string;
};

export async function listStaff(token: string): Promise<StaffRow[]> {
  const r = await staffFetch("/admin/api/v1/staff", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).staff as StaffRow[];
}

export async function createStaff(
  token: string,
  body: { staff_id: string; display_name: string; role: string; password: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/staff", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create failed ${r.status}`);
  }
}

export async function patchStaff(
  token: string,
  staffId: string,
  body: { display_name?: string; role?: string; active?: number },
): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff/${staffId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`patch failed ${r.status}`);
}

export async function resetPassword(token: string, staffId: string, password: string): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff/${staffId}/reset-password`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ password }),
  });
  if (!r.ok) throw new Error(`reset failed ${r.status}`);
}

export const STAFF_ROLES = ["agent", "senior", "supervisor", "engineer", "manager", "admin"];
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/StaffAccountsRoute.tsx
import { useEffect, useState } from "react";

import { createStaff, listStaff, patchStaff, resetPassword, STAFF_ROLES, type StaffRow } from "../../api/adminStaff";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

export function StaffAccountsRoute() {
  const { token, role } = useStaffSession();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ staff_id: "", display_name: "", role: "agent", password: "" });

  function reload() {
    if (!token) return;
    setLoading(true);
    listStaff(token)
      .then(setRows)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function onCreate() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      await createStaff(token, form);
      setForm({ staff_id: "", display_name: "", role: "agent", password: "" });
      setNotice("已创建");
      reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  }

  async function onChangeRole(staffId: string, newRole: string) {
    if (!token) return;
    await patchStaff(token, staffId, { role: newRole });
    reload();
  }

  async function onToggleActive(s: StaffRow) {
    if (!token) return;
    await patchStaff(token, s.staff_id, { active: s.active ? 0 : 1 });
    reload();
  }

  async function onReset(staffId: string) {
    if (!token) return;
    const pw = window.prompt(`为 ${staffId} 设置新密码`);
    if (!pw) return;
    await resetPassword(token, staffId, pw);
    setNotice("密码已重置");
  }

  return (
    <PageContainer width="page">
      <PageHeader title="客服账号" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        role === "admin" && (
          <>
            <Card>
              <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
                <Input placeholder="staff_id" value={form.staff_id}
                  onChange={(e) => setForm({ ...form, staff_id: e.target.value })} className="w-32" />
                <Input placeholder="显示名" value={form.display_name}
                  onChange={(e) => setForm({ ...form, display_name: e.target.value })} className="w-32" />
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="rounded border border-line px-2 py-1 text-body2">
                  {STAFF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
                <Input type="password" placeholder="初始密码" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-32" />
                <Button size="md" onClick={onCreate}
                  disabled={!form.staff_id || !form.display_name || !form.password}>新建</Button>
              </div>
            </Card>

            <Card className="mt-3">
              <div className="overflow-x-auto">
                <table className="w-full text-body3">
                  <thead>
                    <tr className="border-b border-line text-ink-secondary">
                      <th className="px-3 py-2 text-left font-normal">staff_id</th>
                      <th className="px-3 py-2 text-left font-normal">显示名</th>
                      <th className="px-3 py-2 text-left font-normal">角色</th>
                      <th className="px-3 py-2 text-left font-normal">状态</th>
                      <th className="px-3 py-2 text-left font-normal">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((s) => (
                      <tr key={s.staff_id} className="border-b border-line last:border-0">
                        <td className="px-3 py-2 text-ink-primary">{s.staff_id}</td>
                        <td className="px-3 py-2 text-ink-secondary">{s.display_name}</td>
                        <td className="px-3 py-2">
                          <select value={s.role} onChange={(e) => onChangeRole(s.staff_id, e.target.value)}
                            className="rounded border border-line px-1 py-0.5">
                            {STAFF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <span className={s.active ? "text-status-success" : "text-ink-tertiary"}>
                            {s.active ? "启用" : "停用"}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex gap-2">
                            <button className="text-brand" onClick={() => onToggleActive(s)}>
                              {s.active ? "停用" : "启用"}
                            </button>
                            <button className="text-brand" onClick={() => onReset(s.staff_id)}>重置密码</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `StaffAccountsRoute`，在 `<Route element={<StaffLayout />}>` 内加：
```tsx
<Route path="/admin/staff" element={<StaffAccountsRoute />} />
```

- [ ] **Step 4: typecheck + lint + 手动验证**

Run: `cd web && pnpm typecheck && pnpm lint`
Expected: 通过。
手动验证（dev server 跑在主仓库还是 worktree 先 `ps aux | grep vite` 确认）：admin 登录 → 侧栏「客服账号」→ 能列出、新建（试 supervisor）、改角色、停用/启用、重置密码；非 admin 看不到该菜单。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminStaff.ts web/src/routes/admin/StaffAccountsRoute.tsx web/src/App.tsx
git commit -m "feat(admin): 客服账号管理前端页

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 2 — 工单详情页

## Task 2.1: 工单详情 API（复用 get_ticket）

**Files:**
- Modify: `server/src/ai_engine/api/tickets.py`（加端点）
- Test: `server/tests/test_ticket_detail_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_ticket_detail_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff
    from ai_engine.persistence.tickets import append_ticket_event, create_ticket

    await create_staff("AG1", "客服", "agent", "x")
    await create_ticket("T-1", 1, {"category": "billing", "severity": "high"})
    await append_ticket_event("T-1", "in_progress", actor="op1", comment="受理")
    yield {"agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_get_ticket_detail(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/T-1", headers=_h(env["agent"]))
    assert r.status_code == 200
    body = r.json()
    assert body["external_id"] == "T-1"
    assert len(body["events"]) == 1
    assert body["events"][0]["event"] == "in_progress"


async def test_get_ticket_404(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/NOPE", headers=_h(env["agent"]))
    assert r.status_code == 404


async def test_get_ticket_needs_auth(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/T-1")
    assert r.status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_ticket_detail_api.py -v`
Expected: FAIL — `test_get_ticket_detail` 404（端点不存在）。

- [ ] **Step 3: 加端点**

`server/src/ai_engine/api/tickets.py`：在 `staff_list_tickets` 之后追加（`get_ticket` 已在文件顶部 import）：
```python
@router.get("/staff/api/v1/tickets/{external_id}")
async def staff_get_ticket(
    external_id: str, staff: dict[str, Any] = Depends(require_staff)
) -> dict[str, Any]:
    """工单详情（含事件链）。本地只读镜像，外部事项中心为状态真源。"""
    t = await get_ticket(external_id)
    if t is None:
        raise HTTPException(404, "ticket not found")
    return t
```
（`Depends`、`require_staff`、`HTTPException`、`Any` 均已在该文件 import。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd server && pytest tests/test_ticket_detail_api.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/api/tickets.py server/tests/test_ticket_detail_api.py
git commit -m "feat(admin): 工单详情 API（含事件链，复用 get_ticket）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: 工单详情前端页

**Files:**
- Modify: `web/src/api/staff.ts`（追加 getTicketDetail + 类型）
- Create: `web/src/routes/staff/TicketDetailRoute.tsx`
- Modify: `web/src/App.tsx`（路由）
- Modify: `web/src/routes/staff/TicketsRoute.tsx`（行链接到详情）

- [ ] **Step 1: API client（追加到 staff.ts）**

在 `web/src/api/staff.ts` 末尾追加（沿用该文件已有的 `authHeaders`/`staffFetch` 模式；若文件内已有 authHeaders 则复用，否则参照 adminStaff.ts 定义）：
```typescript
export type TicketEvent = {
  event: string;
  actor: string | null;
  comment: string | null;
  created_at: string;
};

export type TicketDetail = {
  external_id: string;
  conversation_id: number;
  payload_json: string;
  current_severity: string | null;
  created_at: string;
  events: TicketEvent[];
};

export async function getTicketDetail(token: string, externalId: string): Promise<TicketDetail> {
  const r = await staffFetch(`/staff/api/v1/tickets/${externalId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (r.status === 404) throw new Error("工单不存在");
  if (!r.ok) throw new Error(`ticket failed ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 详情页组件**

```tsx
// web/src/routes/staff/TicketDetailRoute.tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getTicketDetail, type TicketDetail } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

export function TicketDetailRoute() {
  const { externalId = "" } = useParams();
  const { token } = useStaffSession();
  const [t, setT] = useState<TicketDetail | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getTicketDetail(token, externalId)
      .then(setT)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [token, externalId]);

  let payload: Record<string, unknown> = {};
  if (t) {
    try {
      payload = JSON.parse(t.payload_json);
    } catch {
      payload = {};
    }
  }

  return (
    <PageContainer width="page">
      <PageHeader title={`工单 ${externalId}`} />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        t && (
          <>
            <Card>
              <div className="flex flex-col gap-1 px-page py-block-sm text-body3">
                <div>严重度：{t.current_severity ?? "—"}</div>
                <div>分类：{String(payload.category ?? "—")}</div>
                <div>创建时间：{t.created_at}</div>
                <div>
                  关联会话：
                  <Link className="text-brand" to={`/staff/conversations/${t.conversation_id}/logs`}>
                    #{t.conversation_id}
                  </Link>
                </div>
              </div>
            </Card>

            <div className="mt-4 text-body2 font-medium text-ink-primary">事件链</div>
            <Card className="mt-2">
              <ul className="flex flex-col">
                {t.events.length === 0 && (
                  <li className="px-page py-block-sm text-ink-tertiary">暂无事件</li>
                )}
                {t.events.map((e, i) => (
                  <li key={i} className="border-b border-line px-page py-block-sm last:border-0">
                    <div className="flex justify-between text-body3">
                      <span className="text-ink-primary">{e.event}</span>
                      <span className="text-ink-tertiary">{e.created_at}</span>
                    </div>
                    {(e.actor || e.comment) && (
                      <div className="mt-0.5 text-footnote text-ink-secondary">
                        {e.actor && <span>受理人：{e.actor} </span>}
                        {e.comment && <span>· {e.comment}</span>}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 列表跳转**

`web/src/App.tsx`：import `TicketDetailRoute`，在 StaffLayout 内加：
```tsx
<Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
```
`web/src/routes/staff/TicketsRoute.tsx`：把每行工单的 external_id 包成 `<Link to={`/staff/tickets/${ticket.external_id}`}>`（按该文件现有列表渲染结构插入链接，保持其余不变）。

- [ ] **Step 4: typecheck + lint + 手动验证**

Run: `cd web && pnpm typecheck && pnpm lint`
Expected: 通过。
手动：登录 → 工单列表 → 点一条 → 看到详情 + 事件链 + 跳会话留痕。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/staff.ts web/src/routes/staff/TicketDetailRoute.tsx web/src/App.tsx web/src/routes/staff/TicketsRoute.tsx
git commit -m "feat(admin): 工单详情前端页（事件链 + 跳会话）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 3 — SLA 配置与告警（supervisor/admin）

## Task 3.1: sla_policies 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`（新增表）
- Modify: `server/migrations/versions/<auto>_admin_console_m1.py`（追加建表）
- Test: 由 3.2 的 DAO 测试覆盖；本 Task 跑 parity 测试

- [ ] **Step 1: 加表定义**

`server/src/ai_engine/persistence/schema.py` 末尾追加：
```python
# SLA 策略：接管/解决时长阈值，可按全局/user_type 设。违规为运行时计算，不落表。
sla_policies = Table(
    "sla_policies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("metric", String(32), nullable=False),  # take_time / resolve_time
    Column("threshold_seconds", Integer, nullable=False),
    Column("scope", String(32), nullable=False, server_default="all"),  # all / user_type
    Column("scope_value", String(64)),  # scope=user_type 时为 c/b/g
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "metric IN ('take_time','resolve_time')", name="ck_sla_metric"
    ),
)
```

- [ ] **Step 2: 迁移追加建表**

编辑同一个 admin_console_m1 迁移文件，`upgrade()` 追加：
```python
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("threshold_seconds", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="all"),
        sa.Column("scope_value", sa.String(64), nullable=True),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.CheckConstraint("metric IN ('take_time','resolve_time')", name="ck_sla_metric"),
    )
```
`downgrade()` 追加（在 admin_audit_log 之前）：`op.drop_table("sla_policies")`。

- [ ] **Step 3: 跑 parity 测试**

Run: `cd server && pytest tests/test_alembic_migrations.py -v`
Expected: PASS（sla_policies、admin_audit_log 都出现在 alembic 建表集合）。

- [ ] **Step 4: Commit**

```bash
git add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git commit -m "feat(admin): sla_policies 表 + 迁移

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: SLA persistence（CRUD + 违规计算）

**Files:**
- Create: `server/src/ai_engine/persistence/admin_sla.py`
- Test: `server/tests/test_admin_sla_dao.py`

违规计算口径：复用 `staff_actions`（take/resolved/release/transfer_out）。
- `take_time`：会话 `created_at` → 首条 `take` 的耗时；若至今无 take 则用 now-created_at（仍未接管=进行中违规）。
- `resolve_time`：首条 `take` → 对应 `resolved` 的耗时；未 resolved 用 now-take。
M1 只计「当前未结束且已超阈值」的进行中违规（给告警列表用），保持简单。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_sla_dao.py
from ai_engine.persistence import admin_sla


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_crud_policy(temp_db_url):
    await _init(temp_db_url)
    pid = await admin_sla.create_policy("take_time", 300, "all", None)
    rows = await admin_sla.list_policies()
    assert len(rows) == 1 and rows[0]["id"] == pid
    await admin_sla.set_policy_active(pid, 0)
    assert int((await admin_sla.list_policies())[0]["active"]) == 0


async def test_create_rejects_bad_metric(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await admin_sla.create_policy("bogus", 10, "all", None)


async def test_breaches_detects_untaken_conversation(temp_db_url):
    await _init(temp_db_url)
    from ai_engine.persistence import db
    # 一条很久以前创建、从未接管的会话
    await db.execute(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES ('c','u1','human_pending','2000-01-01 00:00:00')"
    )
    await admin_sla.create_policy("take_time", 60, "all", None)
    breaches = await admin_sla.compute_breaches()
    assert any(b["metric"] == "take_time" for b in breaches)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_sla_dao.py -v`
Expected: FAIL — `ModuleNotFoundError: ai_engine.persistence.admin_sla`。

- [ ] **Step 3: 实现 persistence**

```python
# server/src/ai_engine/persistence/admin_sla.py
"""SLA 策略 CRUD + 进行中违规计算（运行时算，不落 breach 表）。"""

from datetime import UTC, datetime
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

_VALID_METRICS = {"take_time", "resolve_time"}


async def create_policy(metric: str, threshold_seconds: int, scope: str, scope_value: str | None) -> int:
    if metric not in _VALID_METRICS:
        raise ValueError("invalid metric")
    return await db.insert_returning_id(
        "INSERT INTO sla_policies(metric, threshold_seconds, scope, scope_value, created_at) "
        "VALUES (:m, :th, :sc, :sv, :now) RETURNING id",
        {"m": metric, "th": int(threshold_seconds), "sc": scope, "sv": scope_value, "now": now_str()},
    )


async def list_policies() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, metric, threshold_seconds, scope, scope_value, active, created_at "
        "FROM sla_policies ORDER BY id"
    )


async def set_policy_active(policy_id: int, active: int) -> None:
    await db.execute(
        "UPDATE sla_policies SET active = :a WHERE id = :id",
        {"a": int(active), "id": int(policy_id)},
    )


async def delete_policy(policy_id: int) -> None:
    await db.execute("DELETE FROM sla_policies WHERE id = :id", {"id": int(policy_id)})


def _elapsed(since: str) -> float:
    return (datetime.now(UTC).replace(tzinfo=None) - datetime.fromisoformat(since)).total_seconds()


async def compute_breaches() -> list[dict[str, Any]]:
    """当前进行中且已超阈值的违规列表（告警用）。

    take_time: 仍未接管(mode=human_pending 且无 take 记录)且 now-created_at>阈值。
    resolve_time: 已接管(有 take)未 resolved 且 now-take>阈值。
    """
    policies = [p for p in await list_policies() if int(p["active"]) == 1]
    if not policies:
        return []
    take_thr = min((int(p["threshold_seconds"]) for p in policies if p["metric"] == "take_time"), default=None)
    resolve_thr = min((int(p["threshold_seconds"]) for p in policies if p["metric"] == "resolve_time"), default=None)

    breaches: list[dict[str, Any]] = []
    # 进行中会话（未归档）
    convs = await db.fetch_all(
        "SELECT id, user_type, subject_id, mode, created_at FROM conversations WHERE archived = 0"
    )
    for c in convs:
        cid = int(c["id"])
        take = await db.fetch_one(
            "SELECT at FROM staff_actions WHERE conversation_id = :cid AND action = 'take' "
            "ORDER BY id LIMIT 1",
            {"cid": cid},
        )
        ended = await db.fetch_one(
            "SELECT at FROM staff_actions WHERE conversation_id = :cid "
            "AND action IN ('resolved','release','transfer_out') ORDER BY id DESC LIMIT 1",
            {"cid": cid},
        )
        if take_thr is not None and take is None and str(c["mode"]) == "human_pending":
            el = _elapsed(str(c["created_at"]))
            if el > take_thr:
                breaches.append({"conversation_id": cid, "metric": "take_time",
                                 "elapsed_seconds": int(el), "threshold_seconds": take_thr})
        if resolve_thr is not None and take is not None and ended is None:
            el = _elapsed(str(take["at"]))
            if el > resolve_thr:
                breaches.append({"conversation_id": cid, "metric": "resolve_time",
                                 "elapsed_seconds": int(el), "threshold_seconds": resolve_thr})
    return breaches
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_sla_dao.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add server/src/ai_engine/persistence/admin_sla.py server/tests/test_admin_sla_dao.py
git commit -m "feat(admin): SLA 策略 CRUD + 进行中违规计算

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: SLA API

**Files:**
- Create: `server/src/ai_engine/api/admin_sla.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_sla_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_sla_api.py
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
        assert (await c.get("/admin/api/v1/sla/policies", headers=_h(env["agent"]))).status_code == 403


async def test_create_list_policy(env):
    async with await _c() as c:
        r = await c.post("/admin/api/v1/sla/policies",
                         json={"metric": "take_time", "threshold_seconds": 300, "scope": "all"},
                         headers=_h(env["sup"]))
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/sla/policies", headers=_h(env["sup"]))).json()["policies"]
    assert any(p["metric"] == "take_time" for p in listed)


async def test_breaches_endpoint(env):
    from ai_engine.persistence import db
    await db.execute(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES ('c','u1','human_pending','2000-01-01 00:00:00')"
    )
    async with await _c() as c:
        await c.post("/admin/api/v1/sla/policies",
                     json={"metric": "take_time", "threshold_seconds": 60, "scope": "all"},
                     headers=_h(env["sup"]))
        r = await c.get("/admin/api/v1/sla/breaches", headers=_h(env["sup"]))
    assert r.status_code == 200
    assert any(b["metric"] == "take_time" for b in r.json()["breaches"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_sla_api.py -v`
Expected: FAIL — 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_sla.py
"""SLA 配置与告警（supervisor/admin）。写操作落审计。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, admin_sla

router = APIRouter()
_sup = require_roles("supervisor", "admin")


@router.get("/admin/api/v1/sla/policies")
async def list_policies(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"policies": await admin_sla.list_policies()}


class PolicyIn(BaseModel):
    metric: str
    threshold_seconds: int
    scope: str = "all"
    scope_value: str | None = None


@router.post("/admin/api/v1/sla/policies")
async def create_policy(body: PolicyIn, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    try:
        pid = await admin_sla.create_policy(
            body.metric, body.threshold_seconds, body.scope, body.scope_value
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="sla.create",
        target_type="sla_policy", target_id=str(pid), detail=body.model_dump(),
    )
    return {"ok": True, "id": pid}


class PolicyPatchIn(BaseModel):
    active: int


@router.patch("/admin/api/v1/sla/policies/{policy_id}")
async def patch_policy(
    policy_id: int, body: PolicyPatchIn, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await admin_sla.set_policy_active(policy_id, body.active)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="sla.update",
        target_type="sla_policy", target_id=str(policy_id), detail={"active": body.active},
    )
    return {"ok": True}


@router.delete("/admin/api/v1/sla/policies/{policy_id}")
async def delete_policy(policy_id: int, staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    await admin_sla.delete_policy(policy_id)
    await admin_audit.log_admin_action(
        actor=staff.get("sub", "unknown"), action="sla.delete",
        target_type="sla_policy", target_id=str(policy_id),
    )
    return {"ok": True}


@router.get("/admin/api/v1/sla/breaches")
async def list_breaches(staff: dict[str, Any] = Depends(_sup)) -> dict[str, Any]:
    return {"breaches": await admin_sla.compute_breaches()}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_sla import router as admin_sla_router`，加 `app.include_router(admin_sla_router)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_sla_api.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_sla.py server/src/ai_engine/main.py server/tests/test_admin_sla_api.py
git commit -m "feat(admin): SLA 配置/告警 API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.4: SLA 前端页

**Files:**
- Create: `web/src/api/adminSla.ts`
- Create: `web/src/routes/admin/SlaRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminSla.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type SlaPolicy = {
  id: number;
  metric: string;
  threshold_seconds: number;
  scope: string;
  scope_value: string | null;
  active: number;
  created_at: string;
};

export type SlaBreach = {
  conversation_id: number;
  metric: string;
  elapsed_seconds: number;
  threshold_seconds: number;
};

export async function listPolicies(token: string): Promise<SlaPolicy[]> {
  const r = await staffFetch("/admin/api/v1/sla/policies", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).policies;
}

export async function createPolicy(
  token: string,
  body: { metric: string; threshold_seconds: number; scope: string; scope_value?: string | null },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/sla/policies", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create failed ${r.status}`);
}

export async function setPolicyActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/sla/policies/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch failed ${r.status}`);
}

export async function deletePolicy(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/sla/policies/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete failed ${r.status}`);
}

export async function listBreaches(token: string): Promise<SlaBreach[]> {
  const r = await staffFetch("/admin/api/v1/sla/breaches", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`breaches failed ${r.status}`);
  return (await r.json()).breaches;
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/SlaRoute.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  createPolicy, deletePolicy, listBreaches, listPolicies, setPolicyActive,
  type SlaBreach, type SlaPolicy,
} from "../../api/adminSla";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const METRIC_LABEL: Record<string, string> = { take_time: "接管时长", resolve_time: "解决时长" };

export function SlaRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [breaches, setBreaches] = useState<SlaBreach[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ metric: "take_time", threshold_seconds: 300 });

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listPolicies(token), listBreaches(token)])
      .then(([p, b]) => { setPolicies(p); setBreaches(b); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function onCreate() {
    if (!token) return;
    await createPolicy(token, { metric: form.metric, threshold_seconds: Number(form.threshold_seconds), scope: "all" });
    reload();
  }

  return (
    <PageContainer width="page">
      <PageHeader title="SLA 配置与告警" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            {breaches.length > 0 && (
              <Alert variant="error" className="mb-3">
                当前 {breaches.length} 个会话超时未处理
              </Alert>
            )}

            <Card>
              <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
                <select value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })}
                  className="rounded border border-line px-2 py-1 text-body2">
                  <option value="take_time">接管时长</option>
                  <option value="resolve_time">解决时长</option>
                </select>
                <Input type="number" min={1} value={form.threshold_seconds}
                  onChange={(e) => setForm({ ...form, threshold_seconds: Number(e.target.value) })}
                  className="w-28" aria-label="阈值秒数" />
                <span className="text-body3 text-ink-secondary">秒</span>
                <Button size="md" onClick={onCreate}>新增策略</Button>
              </div>
            </Card>

            <div className="mt-4 text-body2 font-medium text-ink-primary">策略</div>
            <Card className="mt-2">
              <table className="w-full text-body3">
                <thead>
                  <tr className="border-b border-line text-ink-secondary">
                    <th className="px-3 py-2 text-left font-normal">指标</th>
                    <th className="px-3 py-2 text-right font-normal">阈值(秒)</th>
                    <th className="px-3 py-2 text-left font-normal">状态</th>
                    <th className="px-3 py-2 text-left font-normal">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((p) => (
                    <tr key={p.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-2 text-ink-primary">{METRIC_LABEL[p.metric] ?? p.metric}</td>
                      <td className="px-3 py-2 text-right text-ink-secondary">{p.threshold_seconds}</td>
                      <td className="px-3 py-2">{p.active ? "启用" : "停用"}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-2">
                          <button className="text-brand" onClick={() => token && setPolicyActive(token, p.id, p.active ? 0 : 1).then(reload)}>
                            {p.active ? "停用" : "启用"}
                          </button>
                          <button className="text-status-error" onClick={() => token && deletePolicy(token, p.id).then(reload)}>删除</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <div className="mt-4 text-body2 font-medium text-ink-primary">当前超时会话</div>
            <Card className="mt-2">
              <ul className="flex flex-col">
                {breaches.length === 0 && <li className="px-page py-block-sm text-ink-tertiary">无</li>}
                {breaches.map((b, i) => (
                  <li key={i} className="flex justify-between border-b border-line px-page py-block-sm last:border-0">
                    <Link className="text-brand" to={`/staff/conversations/${b.conversation_id}`}>
                      会话 #{b.conversation_id}
                    </Link>
                    <span className="text-status-error">
                      {METRIC_LABEL[b.metric]} 已 {b.elapsed_seconds}s / 阈值 {b.threshold_seconds}s
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          </>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `SlaRoute`，StaffLayout 内加 `<Route path="/admin/sla" element={<SlaRoute />} />`。

- [ ] **Step 4: typecheck + lint + 手动验证**

Run: `cd web && pnpm typecheck && pnpm lint`
手动：supervisor 登录 → SLA → 新增 take_time=60s 策略 → 若有久未接管会话，顶部红条 + 列表出现。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminSla.ts web/src/routes/admin/SlaRoute.tsx web/src/App.tsx
git commit -m "feat(admin): SLA 配置与告警前端页

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 4 — 统一审计中心（engineer/admin）

## Task 4.1: 审计查询 API

**Files:**
- Create: `server/src/ai_engine/api/admin_audit.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_audit_api.py`
（查询函数 `list_admin_actions` 已在 Task 0.3 实现。）

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_audit_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import admin_audit
    from ai_engine.persistence.staff import create_staff

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await admin_audit.log_admin_action(actor="AD1", action="staff.create", target_id="X1")
    yield {"eng": issue_staff_token("EN1", "engineer"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_engineer_can_list(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit", headers=_h(env["eng"]))
    assert r.status_code == 200
    assert any(e["action"] == "staff.create" for e in r.json()["entries"])


async def test_filter_by_action(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit?action=sla.update", headers=_h(env["eng"]))
    assert r.status_code == 200
    assert r.json()["entries"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_audit_api.py -v`
Expected: FAIL — 404。

- [ ] **Step 3: 实现路由**

```python
# server/src/ai_engine/api/admin_audit.py
"""统一操作审计查询（engineer/admin）。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit

router = APIRouter()
_eng = require_roles("engineer", "admin")


@router.get("/admin/api/v1/audit")
async def list_audit(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    staff: dict[str, Any] = Depends(_eng),
) -> dict[str, Any]:
    entries = await admin_audit.list_admin_actions(
        actor=actor, action=action, target_type=target_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    return {"entries": entries}
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_audit import router as admin_audit_router`，加 `app.include_router(admin_audit_router)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_audit_api.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_audit.py server/src/ai_engine/main.py server/tests/test_admin_audit_api.py
git commit -m "feat(admin): 统一审计中心查询 API

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.2: 审计中心前端页

**Files:**
- Create: `web/src/api/adminAudit.ts`
- Create: `web/src/routes/admin/AuditCenterRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminAudit.ts
import { staffFetch } from "./staffFetch";

export type AuditEntry = {
  id: number;
  actor: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail_json: string | null;
  created_at: string;
};

export async function listAudit(
  token: string,
  opts?: { actor?: string; action?: string },
): Promise<AuditEntry[]> {
  const qs = new URLSearchParams();
  if (opts?.actor) qs.set("actor", opts.actor);
  if (opts?.action) qs.set("action", opts.action);
  const r = await staffFetch(`/admin/api/v1/audit?${qs.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`audit failed ${r.status}`);
  return (await r.json()).entries;
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/AuditCenterRoute.tsx
import { useEffect, useState } from "react";

import { listAudit, type AuditEntry } from "../../api/adminAudit";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

export function AuditCenterRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState({ actor: "", action: "" });

  function reload() {
    if (!token) return;
    setLoading(true);
    listAudit(token, { actor: filter.actor || undefined, action: filter.action || undefined })
      .then(setEntries)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="page">
      <PageHeader title="操作审计" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
            <Input placeholder="操作人 staff_id" value={filter.actor}
              onChange={(e) => setFilter({ ...filter, actor: e.target.value })} className="w-40" />
            <Input placeholder="动作 如 staff.create" value={filter.action}
              onChange={(e) => setFilter({ ...filter, action: e.target.value })} className="w-44" />
            <Button size="md" onClick={reload}>筛选</Button>
          </div>
        </Card>
      )}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-body3">
                <thead>
                  <tr className="border-b border-line text-ink-secondary">
                    <th className="px-3 py-2 text-left font-normal">时间</th>
                    <th className="px-3 py-2 text-left font-normal">操作人</th>
                    <th className="px-3 py-2 text-left font-normal">动作</th>
                    <th className="px-3 py-2 text-left font-normal">对象</th>
                    <th className="px-3 py-2 text-left font-normal">详情</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">暂无记录</td></tr>
                  )}
                  {entries.map((e) => (
                    <tr key={e.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-2 text-ink-tertiary">{e.created_at}</td>
                      <td className="px-3 py-2 text-ink-primary">{e.actor}</td>
                      <td className="px-3 py-2 text-ink-secondary">{e.action}</td>
                      <td className="px-3 py-2 text-ink-secondary">
                        {e.target_type ? `${e.target_type}:${e.target_id ?? ""}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-ink-tertiary">{e.detail_json ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `AuditCenterRoute`，StaffLayout 内加 `<Route path="/admin/audit" element={<AuditCenterRoute />} />`。

- [ ] **Step 4: typecheck + lint + 手动验证**

Run: `cd web && pnpm typecheck && pnpm lint`
手动：engineer/admin 登录 → 操作审计 → 看到此前账号/SLA 操作记录；按 action 筛选生效。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminAudit.ts web/src/routes/admin/AuditCenterRoute.tsx web/src/App.tsx
git commit -m "feat(admin): 统一审计中心前端页

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 5 — 核心指标大盘（supervisor/manager/admin）

## Task 5.1: 大盘聚合 API（复用 ai_quality + knowledge_gaps）

**Files:**
- Create: `server/src/ai_engine/api/admin_dashboard.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_dashboard_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_dashboard_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("MGR1", "老板", "manager", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {"mgr": issue_staff_token("MGR1", "manager"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/dashboard/overview", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_manager_overview_shape(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/dashboard/overview", headers=_h(env["mgr"]))
    assert r.status_code == 200
    body = r.json()
    for k in ("total_conversations", "handoff_rate", "downvote_rate", "tool_empty_rate",
              "out_of_scope", "failed_turns"):
        assert k in body
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd server && pytest tests/test_admin_dashboard_api.py -v`
Expected: FAIL — 404。

- [ ] **Step 3: 实现路由（thin wrapper 复用现有聚合）**

```python
# server/src/ai_engine/api/admin_dashboard.py
"""核心指标大盘（supervisor/manager/admin）。复用 staff_metrics.ai_quality 聚合，
不重复造轮子；首页一次取齐转人工率/差评率/工具空结果率/超范围/失败回合。"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence.staff_metrics import ai_quality

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


@router.get("/admin/api/v1/dashboard/overview")
async def overview(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    staff: dict[str, Any] = Depends(_view),
) -> dict[str, Any]:
    return await ai_quality(date_from, date_to)
```

- [ ] **Step 4: 注册 router**

`server/src/ai_engine/main.py`：import `from ai_engine.api.admin_dashboard import router as admin_dashboard_router`，加 `app.include_router(admin_dashboard_router)`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd server && pytest tests/test_admin_dashboard_api.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/api/admin_dashboard.py server/src/ai_engine/main.py server/tests/test_admin_dashboard_api.py
git commit -m "feat(admin): 核心指标大盘聚合 API（复用 ai_quality）

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5.2: 大盘前端页（后台首页）

**Files:**
- Create: `web/src/api/adminDashboard.ts`
- Create: `web/src/routes/admin/DashboardRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminDashboard.ts
import { staffFetch } from "./staffFetch";

export type DashboardOverview = {
  total_conversations: number;
  handoff: number;
  handoff_rate: number;
  upvote: number;
  downvote: number;
  downvote_rate: number;
  tool_calls: number;
  tool_empty: number;
  tool_empty_rate: number;
  out_of_scope: number;
  failed_turns: number;
};

export async function getOverview(token: string, opts?: { from?: string }): Promise<DashboardOverview> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  const r = await staffFetch(`/admin/api/v1/dashboard/overview?${qs.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`overview failed ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 页面组件**

```tsx
// web/src/routes/admin/DashboardRoute.tsx
import { useEffect, useState } from "react";

import { getOverview, type DashboardOverview } from "../../api/adminDashboard";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <Card>
      <div className="flex flex-col gap-1 px-page py-block">
        <span className="text-footnote text-ink-secondary">{label}</span>
        <span className={`text-h3 ${danger ? "text-status-error" : "text-ink-primary"}`}>{value}</span>
      </div>
    </Card>
  );
}

export function DashboardRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "manager" || role === "admin";
  const [d, setD] = useState<DashboardOverview | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !allowed) { setErr("需要管理权限"); setLoading(false); return; }
    const from = toUtcParam(new Date(Date.now() - 7 * 24 * 3600 * 1000));
    getOverview(token, { from })
      .then(setD)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

  return (
    <PageContainer width="page">
      <PageHeader title="数据大盘（近 7 天）" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        d && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Stat label="会话总数" value={String(d.total_conversations)} />
            <Stat label="转人工率" value={pct(d.handoff_rate)} danger={d.handoff_rate > 0.3} />
            <Stat label="差评率" value={pct(d.downvote_rate)} danger={d.downvote_rate > 0.2} />
            <Stat label="工具空结果率" value={pct(d.tool_empty_rate)} danger={d.tool_empty_rate > 0.3} />
            <Stat label="超范围提问" value={String(d.out_of_scope)} />
            <Stat label="失败回合" value={String(d.failed_turns)} danger={d.failed_turns > 0} />
          </div>
        )
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由**

`web/src/App.tsx`：import `DashboardRoute`，StaffLayout 内加 `<Route path="/admin/dashboard" element={<DashboardRoute />} />`。

- [ ] **Step 4: typecheck + lint + 手动验证**

Run: `cd web && pnpm typecheck && pnpm lint`
手动：supervisor/manager/admin 登录 → 数据大盘 → 6 个指标卡渲染，异常指标标红。

- [ ] **Step 5: Commit**

```bash
git add web/src/api/adminDashboard.ts web/src/routes/admin/DashboardRoute.tsx web/src/App.tsx
git commit -m "feat(admin): 核心指标大盘前端页

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# 收尾：全量回归

- [ ] **Step 1: 后端全套**

Run: `cd server && make test`
Expected: 全绿，覆盖率 ≥ 75%。若新模块拉低覆盖率，补 1-2 个边界测试（如 admin_sla.compute_breaches 的 resolve_time 分支）。

- [ ] **Step 2: 前端全套**

Run: `cd web && pnpm typecheck && pnpm lint && pnpm test:ci`
Expected: 通过。

- [ ] **Step 3: 真实 Postgres 验证（关键）**

按项目约束，改了 schema/SQL 必须在真实 PG 验证（SQLite 测不出类型歧义/CHECK 重建差异）：
```bash
docker compose up -d --build api
# 用真实 PG 的 DB_URL 跑迁移 + 冒烟
cd server && alembic upgrade head
```
Expected: `alembic upgrade head` 在 PG 无错；admin 接口冒烟（建账号=supervisor、建 SLA 策略、查大盘）返回 200。重点确认 Task 0.1 的 staff CHECK 重建在 PG 正常。

- [ ] **Step 4: 跨端同步检查**

本计划改动集中在 web 后台 + server API，未改 C 端聊天契约 / Flutter。无需同步其它端。（采集类如 presence/agent-rating 属 M2，本计划不涉及。）

---

## M1 完成定义（DoD）

- 角色体系含 supervisor/manager，`require_roles` 守卫各模块；
- 管理后台菜单按角色显示；
- 客服账号可建/改角色/停用/重置密码，操作落审计；
- 工单可看详情 + 事件链 + 跳会话；
- SLA 策略可配，超时会话有告警列表；
- 统一审计中心可查后台所有写操作；
- 数据大盘首页展示 6 项核心指标；
- 后端 `make test` 全绿且覆盖率达标，真实 PG 迁移通过。

## 遗留说明（非 M1 范围，记录以免遗忘）

- Prompt 灰度后端鉴权仍为 `require_admin`（admin only）；spec 把它划归 engineer/admin，统一到 `require_roles("engineer","admin")` 留 M2 一并处理（避免本计划越界改既有鉴权）。
- 账号管理 spec 标注 supervisor 可读；M1 收敛为 admin only 以规避提权设计，supervisor 读权限留 M2。
- SLA 违规仅算「进行中超时」；历史违规统计、超时主动推送（SSE/Lark）留 M2。
