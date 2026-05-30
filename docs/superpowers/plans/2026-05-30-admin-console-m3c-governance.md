# 管理后台 M3c 实施计划 — 治理与遗留

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 M3 治理侧三块：动态 RBAC（角色权限可视化编辑，spec §5.6.b 阶段二）；`daily_token_usage` 拆 by-model 旁路表彻底解决 M2 遗留的"同 subject 同日多模型时 model 只反映最后一次"问题；自定义报表与导出（spec §5.5.c）。

**Architecture:** 沿用既有分层。动态 RBAC 加 `role_permissions` 表，存 `(role, permission_key, allowed)`，配 `require_permission(perm_key)` 依赖；M3c **不**强行把 M1/M2 既有路由从 `require_roles` 迁过去（避免大改），只把"菜单可见性"做成动态——前端从后端 fetch 角色权限矩阵决定菜单显示。By-model 拆表：新增 `daily_token_usage_by_model`，主键 `(subject_id, user_type, date, model)`；写入双写新旧表；成本聚合改读新表。自定义报表用 `report_definitions` 存维度/筛选；API 出 CSV。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind。

---

## 关键约定（沿用 M1/M2/M3a/M3b）

1. 可选筛选 SQL：`(CAST(:p AS TEXT) IS NULL OR col = :p)`。
2. 时间列用 `now_str()`。
3. 新增表 / 改列必须独立 alembic 迁移；不改既有迁移文件。新表必须出现在 parity 测试通过的表集合里。
4. 后端测试：`temp_db_url`/`seeded_db` + `ASGITransport` + `AsyncClient`。
5. 角色 gate：`require_roles(*roles)`（M1）。审计：`admin_audit.log_admin_action`（M1）。
6. 后端单测：`cd server && .venv/bin/python -m pytest tests/xxx.py -v`；ruff：`.venv/bin/ruff check src/<file> tests/<file>`。
7. 前端验证：`pnpm typecheck` + 针对性 `npx eslint`。`max-lines-per-function` ≤80；`PageContainer width="wide"`。
8. git discipline：`main` 分支。工作树 11 modified + 1 untracked 脏文件不动；`git add <精确路径>`；`git -C /Users/sunchenglin/codes/tevau-cs-engine ...` 避路径混乱。
9. commit 中文 + 末尾 Co-Authored-By 行。

---

## M1/M2/M3a/M3b 已交付基线（M3c 直接复用）

- 角色 6 个；`require_roles`；`admin_audit.log_admin_action`。
- M2 成本：`daily_token_usage`（加了 `model` 列，主键仍 `(subject_id, user_type, date)`，覆盖式写入）；`model_pricing` 表；`admin_cost.usage_by_model` 聚合从 `daily_token_usage` GROUP BY model（会丢精度）。
- M2 RBAC 静态矩阵：`web/src/routes/admin/RbacRoute.tsx` 硬编码 `MODULES` + `ROLES`，只读展示。
- 前端 UI 模式：`api/admin*.ts`、`components/ui/*`。

---

## 文件结构总览

**后端新增**：
- `server/src/ai_engine/persistence/rbac.py` — `role_permissions` CRUD + 缓存 + `is_permitted(role, perm_key)` 函数
- `server/src/ai_engine/persistence/cost_by_model.py` — by-model 表写入 + 聚合查询
- `server/src/ai_engine/persistence/reports.py` — 报表定义 CRUD + 执行引擎
- `server/src/ai_engine/api/admin_rbac.py` — RBAC 矩阵 API
- `server/src/ai_engine/api/admin_reports.py` — 报表 API（含 CSV 导出）
- 2 个独立 alembic 迁移（rbac + 拆表）

**后端修改**：
- `server/src/ai_engine/persistence/schema.py` — 新增 3 张表（`role_permissions`、`daily_token_usage_by_model`、`report_definitions`）
- `server/src/ai_engine/main.py` — include 2 个新 router
- `server/src/ai_engine/governance/token_budget.py` — `_record` 双写新表（确认非脏；M2 改过加 model）
- `server/src/ai_engine/persistence/admin_cost.py` — `usage_by_model` 改读新表（确认非脏）
- `server/src/ai_engine/auth/staff_session.py` — 加 `require_permission(perm_key)` 依赖（确认非脏）

**前端新增**：
- `web/src/api/adminRbac.ts`、`adminReports.ts`
- `web/src/routes/admin/ReportsRoute.tsx`

**前端修改**：
- `web/src/routes/admin/RbacRoute.tsx` — 从硬编码只读改为后端 fetch + 可编辑
- `web/src/components/StaffLayout.tsx` — 菜单 roles 仍硬编码（M3c 不动），加 1 个 M3c 菜单项"自定义报表"

---

# Phase 0 — 菜单加项

## Task 0.1: 后台菜单加自定义报表

**Files:**
- Modify: `web/src/components/StaffLayout.tsx`

- [ ] **Step 1: 改 NAV_ITEMS**

import 区加 `FileSpreadsheet`（lucide-react）。NAV_ITEMS 末尾追加：
```typescript
  // M3c 自定义报表
  { to: "/admin/reports", label: "自定义报表", short: "报表", icon: FileSpreadsheet, roles: ["supervisor", "manager", "admin"] },
```

- [ ] **Step 2: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/components/StaffLayout.tsx` → 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/components/StaffLayout.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 后台菜单加自定义报表项" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 1 — 动态 RBAC

## Task 1.1: role_permissions 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

`schema.py` 末尾追加：
```python
# 动态 RBAC（M3c §5.6.b 阶段二）
# (role, permission_key) 唯一；表为空时回退到硬编码默认（与 M2 RbacRoute 矩阵一致）。
role_permissions = Table(
    "role_permissions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role", String(32), nullable=False),
    Column("permission_key", String(64), nullable=False),  # 如 admin.dashboard, admin.staff
    Column("allowed", Integer, nullable=False, server_default="0"),
    Column("updated_by", String(64)),
    Column("updated_at", String(32), nullable=False),
)
Index(
    "ux_role_perm", role_permissions.c.role, role_permissions.c.permission_key,
    unique=True,
)
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "role_permissions"`
编辑：
```python
def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("permission_key", sa.String(64), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index(
        "ux_role_perm", "role_permissions",
        ["role", "permission_key"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_role_perm", table_name="role_permissions")
    op.drop_table("role_permissions")
```

- [ ] **Step 3: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): role_permissions 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.2: rbac persistence + 默认矩阵 + 缓存

**Files:**
- Create: `server/src/ai_engine/persistence/rbac.py`
- Test: `server/tests/test_rbac_dao.py`

设计：
- 模块级 `_DEFAULT_MATRIX: dict[role, dict[perm_key, bool]]`，与 M2 RbacRoute 硬编码矩阵一致
- `is_permitted(role, perm_key)`：先查 DB；缺失回退 `_DEFAULT_MATRIX`
- `list_matrix()`：合并 DB 行与默认矩阵，返回完整 `dict[role, dict[perm_key, bool]]`
- `upsert_many(actor, items)`：批量 upsert，invalidate 缓存

`PERMISSION_KEYS` 与 M2 RbacRoute 的 `MODULES` 一致：
```
admin.dashboard, admin.staff, admin.performance, admin.qa, admin.sla,
admin.tools, admin.cost, admin.audit, admin.prompts, admin.rbac,
admin.staff_groups, admin.presence, admin.shifts, admin.routing,
admin.prompt_editor, admin.knowledge, admin.guardrails, admin.reports
```

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_rbac_dao.py
from ai_engine.persistence import rbac


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()


async def test_default_admin_has_all(temp_db_url):
    await _init(temp_db_url)
    # admin 默认有所有权限
    assert await rbac.is_permitted("admin", "admin.dashboard") is True
    assert await rbac.is_permitted("admin", "admin.cost") is True


async def test_default_agent_has_none(temp_db_url):
    await _init(temp_db_url)
    assert await rbac.is_permitted("agent", "admin.dashboard") is False


async def test_db_overrides_default(temp_db_url):
    await _init(temp_db_url)
    # 显式给 agent 加权限
    await rbac.upsert_many("AD1", [
        {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
    ])
    assert await rbac.is_permitted("agent", "admin.dashboard") is True


async def test_list_matrix_combines_default_and_db(temp_db_url):
    await _init(temp_db_url)
    await rbac.upsert_many("AD1", [
        {"role": "supervisor", "permission_key": "admin.cost", "allowed": 1},
    ])
    matrix = await rbac.list_matrix()
    # admin 默认拿全部
    assert matrix["admin"]["admin.dashboard"] is True
    # supervisor 默认无 admin.cost（M2 仅 engineer/manager/admin 可见），但 DB 改为 1
    assert matrix["supervisor"]["admin.cost"] is True
    # supervisor 默认有 admin.qa
    assert matrix["supervisor"]["admin.qa"] is True
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_rbac_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/rbac.py
"""动态 RBAC：role_permissions DB-first，缺行回退到 _DEFAULT_MATRIX。

_DEFAULT_MATRIX 与 M2 RbacRoute 的硬编码矩阵保持一致，保证 M3c 上线时
表空仍兼容既有可见性；后台前端从该模块拿可编辑矩阵。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

ROLES: list[str] = ["agent", "senior", "supervisor", "engineer", "manager", "admin"]

PERMISSION_KEYS: list[str] = [
    "admin.dashboard",
    "admin.staff",
    "admin.performance",
    "admin.qa",
    "admin.sla",
    "admin.tools",
    "admin.cost",
    "admin.audit",
    "admin.prompts",
    "admin.rbac",
    "admin.staff_groups",
    "admin.presence",
    "admin.shifts",
    "admin.routing",
    "admin.prompt_editor",
    "admin.knowledge",
    "admin.guardrails",
    "admin.reports",
]

# 默认矩阵：与 M2 RbacRoute MODULES + M3a/M3b/M3c 新增菜单 roles 列表一致
_DEFAULT_MATRIX: dict[str, set[str]] = {
    "agent": set(),
    "senior": set(),
    "supervisor": {
        "admin.dashboard", "admin.performance", "admin.qa", "admin.sla",
        "admin.staff_groups", "admin.presence", "admin.shifts", "admin.routing",
        "admin.knowledge", "admin.reports",
    },
    "engineer": {
        "admin.tools", "admin.audit",
        "admin.cost",  # engineer/manager/admin 可见
        "admin.prompt_editor", "admin.knowledge", "admin.guardrails",
    },
    "manager": {"admin.dashboard", "admin.cost", "admin.reports"},
    "admin": set(PERMISSION_KEYS),  # 全部
}


def _default_allowed(role: str, perm_key: str) -> bool:
    return perm_key in _DEFAULT_MATRIX.get(role, set())


_CACHE: dict[tuple[str, str], int] | None = None  # (role, perm_key) → 0/1


def invalidate_cache() -> None:
    global _CACHE
    _CACHE = None


async def _load_cache() -> dict[tuple[str, str], int]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    rows = await db.fetch_all(
        "SELECT role, permission_key, allowed FROM role_permissions"
    )
    _CACHE = {
        (str(r["role"]), str(r["permission_key"])): int(r["allowed"]) for r in rows
    }
    return _CACHE


async def is_permitted(role: str, perm_key: str) -> bool:
    cache = await _load_cache()
    key = (role, perm_key)
    if key in cache:
        return cache[key] == 1
    return _default_allowed(role, perm_key)


async def list_matrix() -> dict[str, dict[str, bool]]:
    """返回 role → perm_key → allowed 的完整矩阵（DB 优先，缺失回退默认）。"""
    cache = await _load_cache()
    out: dict[str, dict[str, bool]] = {}
    for role in ROLES:
        out[role] = {}
        for k in PERMISSION_KEYS:
            db_val = cache.get((role, k))
            out[role][k] = (db_val == 1) if db_val is not None else _default_allowed(role, k)
    return out


async def upsert_many(actor: str, items: list[dict[str, Any]]) -> int:
    n = 0
    now = now_str()
    for it in items:
        role = str(it["role"])
        perm = str(it["permission_key"])
        allowed = int(it.get("allowed", 0))
        existing = await db.fetch_one(
            "SELECT id FROM role_permissions WHERE role = :r AND permission_key = :p",
            {"r": role, "p": perm},
        )
        if existing is None:
            await db.execute(
                "INSERT INTO role_permissions(role, permission_key, allowed, "
                "updated_by, updated_at) VALUES (:r, :p, :a, :by, :now)",
                {"r": role, "p": perm, "a": allowed, "by": actor, "now": now},
            )
        else:
            await db.execute(
                "UPDATE role_permissions SET allowed = :a, updated_by = :by, "
                "updated_at = :now WHERE id = :id",
                {"a": allowed, "by": actor, "now": now, "id": existing["id"]},
            )
        n += 1
    invalidate_cache()
    return n
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_rbac_dao.py -v` (4 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/rbac.py tests/test_rbac_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/rbac.py server/tests/test_rbac_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): RBAC persistence（matrix 默认 + DB 覆盖 + 缓存）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: RBAC API + 审计

**Files:**
- Create: `server/src/ai_engine/api/admin_rbac.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_rbac_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_rbac_api.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import rbac
    from ai_engine.persistence.staff import create_staff

    rbac.invalidate_cache()
    await create_staff("AD1", "管理员", "admin", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "admin": issue_staff_token("AD1", "admin"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    rbac.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_non_admin_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/rbac/matrix", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_admin_get_matrix(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/rbac/matrix", headers=_h(env["admin"]))
    assert r.status_code == 200
    matrix = r.json()["matrix"]
    assert "admin" in matrix and "agent" in matrix
    assert matrix["admin"]["admin.dashboard"] is True
    assert matrix["agent"]["admin.dashboard"] is False


async def test_admin_upsert_then_visible(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.put(
            "/admin/api/v1/rbac/matrix",
            json={"items": [
                {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
            ]},
            headers=_h(env["admin"]),
        )
        assert r.status_code == 200
        matrix = (await c.get("/admin/api/v1/rbac/matrix",
                              headers=_h(env["admin"]))).json()["matrix"]
    assert matrix["agent"]["admin.dashboard"] is True
    audits = await admin_audit.list_admin_actions(action="rbac.upsert", limit=10)
    assert any(a["actor"] == "AD1" for a in audits)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_rbac_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_rbac.py
"""动态 RBAC（admin only）。"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, rbac

router = APIRouter()
_admin = require_roles("admin")


@router.get("/admin/api/v1/rbac/matrix")
async def get_matrix(staff: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    return {
        "matrix": await rbac.list_matrix(),
        "roles": rbac.ROLES,
        "permission_keys": rbac.PERMISSION_KEYS,
    }


class PermItem(BaseModel):
    role: str
    permission_key: str
    allowed: int


class UpsertIn(BaseModel):
    items: list[PermItem]


@router.put("/admin/api/v1/rbac/matrix")
async def upsert(body: UpsertIn, staff: dict[str, Any] = Depends(_admin)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    n = await rbac.upsert_many(actor=actor, items=[it.model_dump() for it in body.items])
    await admin_audit.log_admin_action(
        actor=actor, action="rbac.upsert",
        target_type="role_permissions", target_id=None,
        detail={"count": n},
    )
    return {"ok": True, "count": n}
```

`main.py`：import + `app.include_router(admin_rbac_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_rbac_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_rbac.py src/ai_engine/main.py tests/test_admin_rbac_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_rbac.py server/src/ai_engine/main.py server/tests/test_admin_rbac_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): RBAC 矩阵 API（GET/PUT + 审计 + 缓存失效）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.4: RBAC 前端改为可编辑

**Files:**
- Create: `web/src/api/adminRbac.ts`
- Modify: `web/src/routes/admin/RbacRoute.tsx`（M2 时是硬编码只读，改为 fetch + 可编辑）

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminRbac.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type RbacMatrix = {
  matrix: Record<string, Record<string, boolean>>;
  roles: string[];
  permission_keys: string[];
};

export async function getMatrix(token: string): Promise<RbacMatrix> {
  const r = await staffFetch("/admin/api/v1/rbac/matrix", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`matrix ${r.status}`);
  return r.json();
}

export async function upsertMatrix(
  token: string,
  items: { role: string; permission_key: string; allowed: number }[],
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/rbac/matrix", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ items }),
  });
  if (!r.ok) throw new Error(`upsert ${r.status}`);
}
```

- [ ] **Step 2: 改 RbacRoute.tsx**

完整替换文件（M2 的硬编码版本被 fetch 版本替换）：
```tsx
// web/src/routes/admin/RbacRoute.tsx
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getMatrix, type RbacMatrix, upsertMatrix } from "../../api/adminRbac";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

type LocalMatrix = Record<string, Record<string, boolean>>;

function MatrixGrid({
  matrix, roles, perms, onToggle,
}: {
  matrix: LocalMatrix; roles: string[]; perms: string[];
  onToggle: (role: string, perm: string, v: boolean) => void;
}) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">模块</th>
              {roles.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perms.map((p) => (
              <tr key={p} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{p}</td>
                {roles.map((r) => (
                  <td key={r} className="px-3 py-2 text-center">
                    <input type="checkbox" aria-label={`${p}/${r}`}
                      checked={matrix[r]?.[p] ?? false}
                      onChange={(e) => onToggle(r, p, e.target.checked)} />
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
  const { token, role } = useStaffSession();
  const allowed = role === "admin";
  const [data, setData] = useState<RbacMatrix | null>(null);
  const [local, setLocal] = useState<LocalMatrix>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!token || !allowed) { setErr("需要管理员权限"); setLoading(false); return; }
    setLoading(true);
    getMatrix(token)
      .then((d) => { setData(d); setLocal(d.matrix); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  function toggle(r: string, p: string, v: boolean) {
    setLocal((prev) => ({ ...prev, [r]: { ...prev[r], [p]: v } }));
  }

  const items = useMemo(() => {
    if (!data) return [];
    return data.roles.flatMap((r) => data.permission_keys.map((p) => ({
      role: r, permission_key: p, allowed: local[r]?.[p] ? 1 : 0,
    })));
  }, [data, local]);

  async function save() {
    if (!token) return;
    setErr(""); setNotice("");
    try { await upsertMatrix(token, items); setNotice("已保存（缓存已刷新）"); }
    catch (e) { setErr(e instanceof Error ? e.message : "保存失败"); }
  }

  return (
    <PageContainer width="wide">
      <PageHeader title="角色权限（可编辑）" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      <p className="mb-3 text-body3 text-ink-secondary">
        改完保存后，rbac.is_permitted 即时按新矩阵生效（缓存失效）。改角色仍走
        <Link to="/admin/staff" className="ml-1 text-brand">客服账号</Link>。
        前端菜单可见性目前仍由 StaffLayout.tsx hardcoded roles 决定，权限矩阵
        改动不会立即改变菜单显示（后续 task 让菜单从此矩阵 fetch）。
      </p>
      {loading ? <LoadingState /> : (allowed && data && (
        <>
          <MatrixGrid matrix={local} roles={data.roles} perms={data.permission_keys}
            onToggle={toggle} />
          <div className="mt-3"><Button size="md" onClick={save}>保存</Button></div>
        </>
      ))}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/api/adminRbac.ts src/routes/admin/RbacRoute.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminRbac.ts web/src/routes/admin/RbacRoute.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): RBAC 矩阵前端改为可编辑（fetch + 保存）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

注：本 task 让矩阵可编辑 + 保存生效（`rbac.is_permitted` 即时反映）。**菜单可见性仍由 `StaffLayout.tsx` hardcoded roles 决定**——把菜单也改为 fetch 矩阵的 task 不在 M3c 范围（涉及 StaffLayout 主结构改造 + 心跳/无 token 时不 fetch 的逻辑），留 M4。当前价值：操作审计有迹可循、后端 `is_permitted` 可被未来接入。

---

# Phase 2 — daily_token_usage by-model 拆表

## Task 2.1: 新表 + 迁移（含历史数据回填）

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

- [ ] **Step 1: 加表定义**

`schema.py` 末尾追加：
```python
# By-model 拆分表（M3c）：彻底解决 M2 同 subject 同日多模型时 model 列被覆盖的问题。
# 主键含 model；写入双写（旧表保留作向后兼容期间的备用）。
daily_token_usage_by_model = Table(
    "daily_token_usage_by_model",
    metadata,
    Column("subject_id", String(128), primary_key=True),
    Column("user_type", String(8), primary_key=True),
    Column("date", String(16), primary_key=True),
    Column("model", String(32), primary_key=True),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
)
```

- [ ] **Step 2: 建迁移（含历史回填）**

Run: `cd server && .venv/bin/python -m alembic revision -m "token_usage_by_model_table"`
编辑：
```python
def upgrade() -> None:
    op.create_table(
        "daily_token_usage_by_model",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("user_type", sa.String(8), primary_key=True),
        sa.Column("date", sa.String(16), primary_key=True),
        sa.Column("model", sa.String(32), primary_key=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    # 历史数据回填：旧表中 model 非空的行直接搬迁；NULL model 行视为 '(unknown)'
    op.execute(
        "INSERT INTO daily_token_usage_by_model"
        "(subject_id, user_type, date, model, input_tokens, output_tokens) "
        "SELECT subject_id, user_type, date, "
        "COALESCE(model, '(unknown)') AS model, "
        "input_tokens, output_tokens "
        "FROM daily_token_usage"
    )


def downgrade() -> None:
    op.drop_table("daily_token_usage_by_model")
```

- [ ] **Step 3: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): daily_token_usage_by_model 表 + 迁移（含历史回填）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: 写入双写 + 成本聚合改读新表

**Files:**
- Modify: `server/src/ai_engine/governance/token_budget.py`（**先 grep 确认非脏**；M2 改过加 model 参数）
- Modify: `server/src/ai_engine/persistence/admin_cost.py`（**先 grep 确认非脏**；M2 实现）
- Test: `server/tests/test_token_usage_by_model.py`

- [ ] **Step 1: 确认非脏 + 读现状**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/governance/token_budget.py server/src/ai_engine/persistence/admin_cost.py`
Expected: 无输出。

读 `server/src/ai_engine/governance/token_budget.py` 看 M2 之后的 `_record` 实现。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_token_usage_by_model.py
async def test_record_double_writes_by_model_table(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    # 新表也有该行
    row = await db.fetch_one(
        "SELECT input_tokens, output_tokens FROM daily_token_usage_by_model "
        "WHERE subject_id='BU1' AND user_type='b' AND model='claude-sonnet-4-6'"
    )
    assert row is not None
    assert int(row["input_tokens"]) == 100
    assert int(row["output_tokens"]) == 50


async def test_same_subject_two_models_keep_separate(temp_db_url):
    """同 subject 同日用两个 model：新表有两行（这是 M3c 的核心修复点）。"""
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU2", 1000, 500, model="claude-sonnet-4-6")
    await check_and_record("b", "BU2", 200, 100, model="claude-haiku-4-5")
    rows = await db.fetch_all(
        "SELECT model, input_tokens, output_tokens FROM daily_token_usage_by_model "
        "WHERE subject_id='BU2' AND user_type='b' ORDER BY model"
    )
    by = {r["model"]: r for r in rows}
    assert int(by["claude-sonnet-4-6"]["input_tokens"]) == 1000
    assert int(by["claude-haiku-4-5"]["input_tokens"]) == 200


async def test_admin_cost_usage_reads_by_model_table(temp_db_url):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import admin_cost
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU3", 1000, 500, model="claude-sonnet-4-6")
    await check_and_record("b", "BU3", 200, 100, model="claude-haiku-4-5")
    rows = await admin_cost.usage_by_model(None, None)
    by = {r["model"]: r for r in rows}
    # 两个 model 都精确（而非 M2 时只反映"最后一次"）
    assert by["claude-sonnet-4-6"]["input_tokens"] == 1000
    assert by["claude-haiku-4-5"]["input_tokens"] == 200
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_token_usage_by_model.py -v` → 部分 FAIL（写入未双写，聚合仍读旧表）。

- [ ] **Step 4: 改 token_budget.py 加双写**

读 `server/src/ai_engine/governance/token_budget.py` 的 `_record` 实现。在写完旧表后追加一条写新表（仅当 model 非 None 时）：
```python
async def _record(subject_id, user_type, day, in_tok, out_tok, model=None):
    # ... 既有写旧表的 INSERT ... ON CONFLICT DO UPDATE 不动 ...

    # M3c: 双写 by-model 拆分表（model None 时跳过新表写入；旧表行为不变）
    if model:
        await db.execute(
            "INSERT INTO daily_token_usage_by_model"
            "(subject_id, user_type, date, model, input_tokens, output_tokens) "
            "VALUES (:s, :u, :d, :m, :it, :ot) "
            "ON CONFLICT(subject_id, user_type, date, model) DO UPDATE SET "
            "input_tokens = daily_token_usage_by_model.input_tokens + :it, "
            "output_tokens = daily_token_usage_by_model.output_tokens + :ot",
            {"s": subject_id, "u": user_type, "d": day,
             "m": model, "it": int(in_tok), "ot": int(out_tok)},
        )
```
保留旧表 INSERT 不变（用于"无 model"路径以及兼容期）。

- [ ] **Step 5: 改 admin_cost.usage_by_model 改读新表**

读 `server/src/ai_engine/persistence/admin_cost.py`。把 `usage_by_model` 中 `FROM daily_token_usage` 改为 `FROM daily_token_usage_by_model`（其它逻辑——单价换算、CAST 过滤等——保留）。

由于新表 model 不会是 NULL（写入时 None 跳过；历史回填 NULL→'(unknown)'），可以把 `COALESCE(model, '(unknown)')` 简化为 `model`：
```python
"SELECT model, SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
"FROM daily_token_usage_by_model "
"WHERE (CAST(:df AS TEXT) IS NULL OR date >= :df) "
"AND (CAST(:dt AS TEXT) IS NULL OR date <= :dt) "
"AND (CAST(:ut AS TEXT) IS NULL OR user_type = :ut) "
"GROUP BY model "
"ORDER BY model"
```

- [ ] **Step 6: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_token_usage_by_model.py tests/test_token_budget.py tests/test_token_budget_model.py tests/test_admin_cost_dao.py tests/test_admin_cost_api.py -v`
Expected: 新测试 pass；既有 token/cost 测试不退化。
Run: `cd server && .venv/bin/ruff check src/ai_engine/governance/token_budget.py src/ai_engine/persistence/admin_cost.py tests/test_token_usage_by_model.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/governance/token_budget.py server/src/ai_engine/persistence/admin_cost.py server/tests/test_token_usage_by_model.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): token 写入双写 by-model 表 + 成本聚合改读新表（彻底解决 M2 model 覆盖问题）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 3 — 自定义报表与导出

## Task 3.1: report_definitions 表 + 迁移

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py`
- Create: 新 alembic 迁移

设计：
- 报表定义 = (name, source, dims_json, filters_json)
- `source` 枚举：`agent_ratings`, `qa_reviews`, `staff_actions`, `daily_token_usage_by_model`, `tool_audits`, `admin_audit_log`
- `dims_json`: 维度数组（如 ["staff_id", "date"]）；执行时 GROUP BY 这些列
- `filters_json`: 过滤数组（如 [{"col":"date","op":">=","val":"2026-06-01"}]）
- `metrics`：默认 `count(*) AS n`（M3c 简化），可选 `sum(<列>)`，由前端选

- [ ] **Step 1: 加表定义 + 迁移**

`schema.py` 末尾追加：
```python
# 自定义报表定义（M3c §5.5.c）
# 执行：按 dims_json GROUP BY，按 filters_json WHERE，metrics 当前固定 count(*) AS n + 可选 sum 字段。
report_definitions = Table(
    "report_definitions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("source", String(64), nullable=False),  # 表名（白名单）
    Column("dims_json", Text, nullable=False, server_default="[]"),
    Column("filters_json", Text, nullable=False, server_default="[]"),
    Column("metrics_json", Text, nullable=False, server_default='[{"op":"count","col":"*","alias":"n"}]'),
    Column("owner", String(64)),
    Column("created_at", String(32), nullable=False),
)
Index("idx_reports_owner", report_definitions.c.owner)
```

Run: `cd server && .venv/bin/python -m alembic revision -m "report_definitions"`
编辑：
```python
def upgrade() -> None:
    op.create_table(
        "report_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("dims_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("filters_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "metrics_json", sa.Text(), nullable=False,
            server_default='[{"op":"count","col":"*","alias":"n"}]',
        ),
        sa.Column("owner", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_reports_owner", "report_definitions", ["owner"])


def downgrade() -> None:
    op.drop_index("idx_reports_owner", table_name="report_definitions")
    op.drop_table("report_definitions")
```

- [ ] **Step 2: parity + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py -v` (2 pass)
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): report_definitions 表 + 迁移" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: 报表 persistence + 执行引擎（白名单 SQL 构造）

**Files:**
- Create: `server/src/ai_engine/persistence/reports.py`
- Test: `server/tests/test_reports_dao.py`

安全核心：报表执行用白名单 source 表名、白名单维度列名、白名单 metric 列名+op、白名单 filter op。所有 dim/col 名先验证是否在白名单中，未通过验证直接抛错；filter value 走绑定参数。**绝不**用字符串拼接用户输入到 SQL 中。

支持的 source（M3c 最小集，可后续扩）：
```
agent_ratings        — 列：staff_id, user_type, rating, created_at
qa_reviews           — 列：reviewer_staff_id, score, tags, created_at
staff_actions        — 列：staff_id, action, at
daily_token_usage_by_model — 列：subject_id, user_type, date, model, input_tokens, output_tokens
tool_audits          — 列：tool_name, rejected, is_empty, created_at
```

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_reports_dao.py
import json

from ai_engine.persistence import reports


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_definition_crud(temp_db_url):
    await _init(temp_db_url)
    rid = await reports.create_definition(
        name="按客服满意度",
        source="agent_ratings",
        dims=["staff_id"],
        filters=[],
        metrics=[{"op": "count", "col": "*", "alias": "n"}, {"op": "avg", "col": "rating", "alias": "avg_rating"}],
        owner="SUP1",
    )
    rows = await reports.list_definitions()
    assert any(r["id"] == rid for r in rows)


async def test_execute_simple_count_by_staff(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG1', 'u2', 'c', 4, '2026-06-01 01:00:00'), "
        "(3, 'AG2', 'u3', 'c', 3, '2026-06-01 02:00:00')"
    )
    result = await reports.execute(
        source="agent_ratings",
        dims=["staff_id"],
        filters=[],
        metrics=[{"op": "count", "col": "*", "alias": "n"},
                 {"op": "avg", "col": "rating", "alias": "avg_rating"}],
    )
    by = {row["staff_id"]: row for row in result["rows"]}
    assert by["AG1"]["n"] == 2
    assert by["AG2"]["n"] == 1


async def test_execute_with_filter(temp_db_url):
    from ai_engine.persistence import db
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG2', 'u2', 'c', 3, '2026-06-01 01:00:00')"
    )
    result = await reports.execute(
        source="agent_ratings",
        dims=["staff_id"],
        filters=[{"col": "rating", "op": ">=", "val": 4}],
        metrics=[{"op": "count", "col": "*", "alias": "n"}],
    )
    assert len(result["rows"]) == 1
    assert result["rows"][0]["staff_id"] == "AG1"


async def test_execute_rejects_unknown_source(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await reports.execute(
            source="evil_table",
            dims=[],
            filters=[],
            metrics=[{"op": "count", "col": "*", "alias": "n"}],
        )


async def test_execute_rejects_unknown_dim(temp_db_url):
    await _init(temp_db_url)
    import pytest
    with pytest.raises(ValueError):
        await reports.execute(
            source="agent_ratings",
            dims=["evil_column"],
            filters=[],
            metrics=[{"op": "count", "col": "*", "alias": "n"}],
        )
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_reports_dao.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/reports.py
"""自定义报表：CRUD + 安全执行引擎。

执行用白名单 source 表 / 维度列 / metric op / filter op；所有 filter value 走绑定参数。
不接受任意字符串拼接 SQL。
"""

import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str

# source 白名单：表名 → 允许的列名集合
_SOURCES: dict[str, set[str]] = {
    "agent_ratings": {
        "id", "conversation_id", "staff_id", "subject_id", "user_type",
        "rating", "created_at",
    },
    "qa_reviews": {
        "id", "conversation_id", "reviewer_staff_id", "scorecard_id",
        "score", "tags", "created_at",
    },
    "staff_actions": {"id", "conversation_id", "staff_id", "action", "at"},
    "daily_token_usage_by_model": {
        "subject_id", "user_type", "date", "model",
        "input_tokens", "output_tokens",
    },
    "tool_audits": {
        "id", "conversation_id", "tool_name", "rejected", "is_empty",
        "subject_id", "user_type", "created_at",
    },
}

_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<=", "LIKE"}
_METRIC_OPS = {"count", "sum", "avg", "min", "max"}


def _validate_dims(source: str, dims: list[str]) -> None:
    cols = _SOURCES.get(source)
    if cols is None:
        raise ValueError(f"unknown source: {source}")
    for d in dims:
        if d not in cols:
            raise ValueError(f"unknown dim {d} in source {source}")


def _validate_metrics(source: str, metrics: list[dict[str, Any]]) -> None:
    cols = _SOURCES.get(source, set())
    for m in metrics:
        op = m.get("op", "")
        col = m.get("col", "")
        if op not in _METRIC_OPS:
            raise ValueError(f"unknown metric op: {op}")
        if col != "*" and col not in cols:
            raise ValueError(f"unknown metric col {col} in source {source}")


def _validate_filters(source: str, filters: list[dict[str, Any]]) -> None:
    cols = _SOURCES.get(source, set())
    for f in filters:
        col = f.get("col", "")
        op = f.get("op", "")
        if col not in cols:
            raise ValueError(f"unknown filter col {col} in source {source}")
        if op not in _FILTER_OPS:
            raise ValueError(f"unknown filter op: {op}")


async def create_definition(
    name: str,
    source: str,
    dims: list[str],
    filters: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    owner: str,
) -> int:
    _validate_dims(source, dims)
    _validate_filters(source, filters)
    _validate_metrics(source, metrics)
    return await db.insert_returning_id(
        "INSERT INTO report_definitions(name, source, dims_json, filters_json, "
        "metrics_json, owner, created_at) "
        "VALUES (:n, :s, :d, :f, :m, :o, :now) RETURNING id",
        {
            "n": name, "s": source,
            "d": json.dumps(dims, ensure_ascii=False),
            "f": json.dumps(filters, ensure_ascii=False),
            "m": json.dumps(metrics, ensure_ascii=False),
            "o": owner, "now": now_str(),
        },
    )


async def list_definitions() -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, name, source, dims_json, filters_json, metrics_json, owner, created_at "
        "FROM report_definitions ORDER BY id DESC"
    )


async def get_definition(report_id: int) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, name, source, dims_json, filters_json, metrics_json, owner, created_at "
        "FROM report_definitions WHERE id = :id",
        {"id": int(report_id)},
    )


async def delete_definition(report_id: int) -> None:
    await db.execute(
        "DELETE FROM report_definitions WHERE id = :id", {"id": int(report_id)}
    )


async def execute(
    source: str,
    dims: list[str],
    filters: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    limit: int = 1000,
) -> dict[str, Any]:
    """构造 SQL 执行。所有结构字段经白名单验证；filter value 走绑定参数。"""
    _validate_dims(source, dims)
    _validate_filters(source, filters)
    _validate_metrics(source, metrics)

    select_parts: list[str] = list(dims)
    for m in metrics:
        op = str(m["op"]).upper()
        col = str(m["col"])
        alias = str(m.get("alias", f"{op}_{col}"))
        # alias 也需是合法标识符：限制为字母数字下划线
        if not alias.replace("_", "").isalnum():
            raise ValueError(f"invalid alias: {alias}")
        if col == "*":
            select_parts.append(f"{op}(*) AS {alias}")
        else:
            select_parts.append(f"{op}({col}) AS {alias}")

    where_clauses: list[str] = []
    binds: dict[str, Any] = {"_lim": int(limit)}
    for i, f in enumerate(filters):
        col = str(f["col"])
        op = str(f["op"])
        key = f"v{i}"
        where_clauses.append(f"{col} {op} :{key}")
        binds[key] = f["val"]

    sql = f"SELECT {', '.join(select_parts)} FROM {source}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if dims:
        sql += " GROUP BY " + ", ".join(dims)
    sql += " LIMIT :_lim"

    rows = await db.fetch_all(sql, binds)
    return {"sql": sql, "rows": rows}
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_reports_dao.py -v` (5 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/reports.py tests/test_reports_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/reports.py server/tests/test_reports_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 自定义报表 persistence（CRUD + 白名单 SQL 安全执行）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: 报表 API + CSV 导出

**Files:**
- Create: `server/src/ai_engine/api/admin_reports.py`
- Modify: `server/src/ai_engine/main.py`
- Test: `server/tests/test_admin_reports_api.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_reports_api.py
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
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG2', 'u2', 'c', 3, '2026-06-01 01:00:00')"
    )
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
        r = await c.get("/admin/api/v1/reports", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_run_export_csv(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/reports",
            json={
                "name": "按客服评分",
                "source": "agent_ratings",
                "dims": ["staff_id"],
                "filters": [],
                "metrics": [{"op": "count", "col": "*", "alias": "n"}],
            },
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        run = await c.post(f"/admin/api/v1/reports/{rid}/run", headers=_h(env["sup"]))
        assert run.status_code == 200
        rows = run.json()["rows"]
        by = {row["staff_id"]: row for row in rows}
        assert by["AG1"]["n"] == 1
        # CSV 导出
        csv = await c.get(f"/admin/api/v1/reports/{rid}/export.csv", headers=_h(env["sup"]))
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    text = csv.text
    assert "staff_id" in text and "AG1" in text


async def test_create_rejects_bad_source(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/reports",
            json={
                "name": "x", "source": "evil", "dims": [], "filters": [],
                "metrics": [{"op": "count", "col": "*", "alias": "n"}],
            },
            headers=_h(env["sup"]),
        )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_reports_api.py -v` → 404。

- [ ] **Step 3: 实现路由 + 注册**

```python
# server/src/ai_engine/api/admin_reports.py
"""自定义报表（supervisor/manager/admin）。"""

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_engine.auth.staff_session import require_roles
from ai_engine.persistence import admin_audit, reports

router = APIRouter()
_view = require_roles("supervisor", "manager", "admin")


class DefIn(BaseModel):
    name: str
    source: str
    dims: list[str] = []
    filters: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = [{"op": "count", "col": "*", "alias": "n"}]


@router.get("/admin/api/v1/reports")
async def list_defs(staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return {"definitions": await reports.list_definitions()}


@router.post("/admin/api/v1/reports")
async def create_def(body: DefIn, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    actor = str(staff.get("sub", "unknown"))
    try:
        rid = await reports.create_definition(
            name=body.name, source=body.source,
            dims=body.dims, filters=body.filters, metrics=body.metrics,
            owner=actor,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await admin_audit.log_admin_action(
        actor=actor, action="report.create",
        target_type="report", target_id=str(rid), detail={"name": body.name},
    )
    return {"ok": True, "id": rid}


@router.delete("/admin/api/v1/reports/{report_id}")
async def delete_def(report_id: int, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    await reports.delete_definition(report_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="report.delete",
        target_type="report", target_id=str(report_id),
    )
    return {"ok": True}


async def _run(report_id: int) -> dict[str, Any]:
    d = await reports.get_definition(report_id)
    if d is None:
        raise HTTPException(404, "report not found")
    try:
        return await reports.execute(
            source=str(d["source"]),
            dims=json.loads(str(d["dims_json"])),
            filters=json.loads(str(d["filters_json"])),
            metrics=json.loads(str(d["metrics_json"])),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/api/v1/reports/{report_id}/run")
async def run_def(report_id: int, staff: dict[str, Any] = Depends(_view)) -> dict[str, Any]:
    return await _run(report_id)


@router.get("/admin/api/v1/reports/{report_id}/export.csv")
async def export_csv(report_id: int, staff: dict[str, Any] = Depends(_view)) -> StreamingResponse:
    result = await _run(report_id)
    rows = result["rows"]
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.csv"'},
    )
```

`main.py`：import + `app.include_router(admin_reports_router)`。

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_reports_api.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_reports.py src/ai_engine/main.py tests/test_admin_reports_api.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_reports.py server/src/ai_engine/main.py server/tests/test_admin_reports_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 自定义报表 API（CRUD + run + CSV 导出 + 审计）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.4: 报表前端页

**Files:**
- Create: `web/src/api/adminReports.ts`
- Create: `web/src/routes/admin/ReportsRoute.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: API client**

```typescript
// web/src/api/adminReports.ts
import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ReportDef = {
  id: number;
  name: string;
  source: string;
  dims_json: string;
  filters_json: string;
  metrics_json: string;
  owner: string | null;
  created_at: string;
};

export type ReportResult = {
  sql: string;
  rows: Record<string, string | number | null>[];
};

export async function listReports(token: string): Promise<ReportDef[]> {
  const r = await staffFetch("/admin/api/v1/reports", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).definitions;
}

export async function createReport(
  token: string,
  body: {
    name: string;
    source: string;
    dims: string[];
    filters: { col: string; op: string; val: string | number }[];
    metrics: { op: string; col: string; alias: string }[];
  },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/reports", {
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

export async function runReport(token: string, id: number): Promise<ReportResult> {
  const r = await staffFetch(`/admin/api/v1/reports/${id}/run`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`run ${r.status}`);
  return r.json();
}

export async function deleteReport(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/reports/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}

export function exportCsvUrl(id: number): string {
  return `/admin/api/v1/reports/${id}/export.csv`;
}
```

- [ ] **Step 2: ReportsRoute**

```tsx
// web/src/routes/admin/ReportsRoute.tsx
import { useEffect, useState } from "react";

import {
  createReport, deleteReport, exportCsvUrl, listReports, type ReportDef, type ReportResult, runReport,
} from "../../api/adminReports";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const SOURCES = [
  "agent_ratings",
  "qa_reviews",
  "staff_actions",
  "daily_token_usage_by_model",
  "tool_audits",
];

function ReportForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [source, setSource] = useState("agent_ratings");
  const [dimsRaw, setDimsRaw] = useState('["staff_id"]');
  const [metricsRaw, setMetricsRaw] = useState('[{"op":"count","col":"*","alias":"n"}]');
  async function submit() {
    if (!token || !name) return;
    let dims: string[];
    let metrics: { op: string; col: string; alias: string }[];
    try {
      dims = JSON.parse(dimsRaw);
      metrics = JSON.parse(metricsRaw);
    } catch { onError("dims/metrics JSON 格式错"); return; }
    try {
      await createReport(token, { name, source, dims, filters: [], metrics });
      setName("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="报表名称" value={name} className="w-60"
            onChange={(e) => setName(e.target.value)} />
          <select value={source} onChange={(e) => setSource(e.target.value)}
            className="rounded border border-line px-2 py-1 text-body2">
            {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Button size="md" onClick={submit} disabled={!name}>新建报表</Button>
        </div>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={2} value={dimsRaw} aria-label="dims JSON"
          onChange={(e) => setDimsRaw(e.target.value)} />
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={2} value={metricsRaw} aria-label="metrics JSON"
          onChange={(e) => setMetricsRaw(e.target.value)} />
      </div>
    </Card>
  );
}

function ResultPanel({ result }: { result: ReportResult | null }) {
  if (!result) return null;
  const cols = result.rows[0] ? Object.keys(result.rows[0]) : [];
  return (
    <Card className="mt-3">
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              {cols.map((c) => (
                <th key={c} className="px-3 py-2 text-left font-normal">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.length === 0 && (
              <tr><td colSpan={Math.max(cols.length, 1)} className="px-3 py-4 text-center text-ink-tertiary">无结果</td></tr>
            )}
            {result.rows.map((row, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                {cols.map((c) => (
                  <td key={c} className="px-3 py-2 text-ink-primary">{String(row[c] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-page py-block-sm text-footnote text-ink-tertiary font-mono">SQL: {result.sql}</p>
    </Card>
  );
}

function ReportRow({ d, onChanged, onError, onResult }: {
  d: ReportDef; onChanged: () => void;
  onError: (m: string) => void; onResult: (r: ReportResult) => void;
}) {
  const { token } = useStaffSession();
  async function run() {
    if (!token) return;
    try { onResult(await runReport(token, d.id)); }
    catch (e) { onError(e instanceof Error ? e.message : "执行失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteReport(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{d.id}</td>
      <td className="px-3 py-2 text-ink-primary">{d.name}</td>
      <td className="px-3 py-2">{d.source}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.owner ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={run}>运行</button>
          <a className="text-brand" href={exportCsvUrl(d.id)} target="_blank" rel="noreferrer">CSV</a>
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function ReportsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "manager" || role === "admin";
  const [reports, setReports] = useState<ReportDef[]>([]);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listReports(token).then(setReports).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管/管理层/管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="自定义报表" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <ReportForm onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <Card className="mt-3">
          <table className="w-full text-body3">
            <thead>
              <tr className="border-b border-line text-ink-secondary">
                <th className="px-3 py-2 text-left font-normal">ID</th>
                <th className="px-3 py-2 text-left font-normal">名称</th>
                <th className="px-3 py-2 text-left font-normal">数据源</th>
                <th className="px-3 py-2 text-left font-normal">owner</th>
                <th className="px-3 py-2 text-left font-normal">操作</th>
              </tr>
            </thead>
            <tbody>
              {reports.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">无报表</td></tr>
              )}
              {reports.map((d) => (
                <ReportRow key={d.id} d={d} onChanged={reload} onError={setErr} onResult={setResult} />
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {result && <ResultPanel result={result} />}
    </PageContainer>
  );
}
```

- [ ] **Step 3: 注册路由 + 验证 + commit**

`web/src/App.tsx`：import `ReportsRoute` + `<Route path="/admin/reports" element={<ReportsRoute />} />`。

Run: `cd web && pnpm typecheck && npx eslint src/api/adminReports.ts src/routes/admin/ReportsRoute.tsx src/App.tsx`
Expected: 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/api/adminReports.ts web/src/routes/admin/ReportsRoute.tsx web/src/App.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 自定义报表前端页（构建/运行/导出 CSV）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# 收尾回归

- [ ] **Step 1: 后端全套**

Run: `cd server && .venv/bin/pytest --cov=src/ai_engine --cov-report=term --cov-fail-under=75 2>&1 | tail -25`
Expected: 全部新增 pass；覆盖率 ≥75%；pre-existing `test_user_upload_and_view` 仍失败保持。

- [ ] **Step 2: 前端检查**

Run: `cd web && pnpm typecheck`
Run: `cd web && pnpm test:ci`
Expected: 仅 pre-existing 错误保持，无新引入。

- [ ] **Step 3: alembic 单 head**

Run: `cd server && .venv/bin/python -m alembic heads`
Expected: 单 head（M3c 3 个迁移：role_permissions、token_usage_by_model_table、report_definitions）。

- [ ] **Step 4: git status 核对**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short`
Expected: 仅 11 modified + 1 untracked。

- [ ] **Step 5: 提交链**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine log --oneline -25`

---

## M3c 完成定义（DoD）

- 动态 RBAC：`role_permissions` 表 + `is_permitted/list_matrix/upsert_many`；表空时回退默认矩阵（与 M2 一致）；admin 可编辑保存（`is_permitted` 立即生效）；前端从硬编码改为 fetch + 可编辑。
- By-model 拆表：`daily_token_usage_by_model` 主键含 model；token 写入双写新表；成本聚合改读新表；历史数据回填。
- 自定义报表：定义表 + 白名单安全执行引擎（source/dim/metric/filter 全白名单）+ CRUD + run + CSV 导出。
- 后端覆盖率 ≥75%；alembic 单 head；新增 3 张表迁移通过 parity。

## 遗留说明（非 M3c 范围）

1. **StaffLayout 菜单仍 hardcoded roles**：M3c 让 RBAC 矩阵可编辑保存到 DB，`is_permitted` 即时生效，但**前端菜单可见性**仍由 `StaffLayout.NAV_ITEMS` 的硬编码 roles 决定。改为从矩阵 fetch 涉及 layout 主结构改造（加载时机、空 token 时不 fetch 等），留 M4。当前价值：审计有迹可循 + 后端 is_permitted 可被未来接入。
2. **既有路由仍用 require_roles**：M3c 不强迁 M1/M2 admin 路由从 `require_roles` 到 `require_permission`。`is_permitted` 是 helper，新代码可选用；旧路由保持稳定。M4 视需要做整迁。
3. **daily_token_usage 旧表仍在双写**：M3c 保留旧表（兼容期）。M4 可选删旧表 + 更新所有依赖点（需 grep `daily_token_usage` 找到所有读取处确认无遗漏）。
4. **报表执行 metrics 仅 count/sum/avg/min/max**：复杂指标（百分位、对比等）需要扩 `_METRIC_OPS`，或加 derived metric 概念。M4 视需要扩。
5. **报表 filter value 类型**：当前测试用整数；字符串/日期值依赖前端正确传 JSON。前端可加类型提示。
6. **CSV 导出大数据集**：M3c 一次性内存缓冲；大报表（数十万行）需流式分片，M4 视需要做。
