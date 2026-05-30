# 管理后台 M4 实施计划 — 收口遗留

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收口 M1-M3 所有"留 M4"遗留：菜单/权限动态化、成本/报表完善、小修补（排班/心跳/locale/审批）、chat.py 整理后的自动接入（路由匹配/guardrails/被动满意度/AI 脱敏）。

**Architecture:** 沿用既有分层。M4 分四个主题：A) chat.py 整理后的自动接入（强依赖前置）；B) 菜单与权限动态化（让 RBAC 矩阵真正驱动菜单）；C) 成本/报表完善（旧表删除、扩 metrics、CSV 流式、UI 类型提示）；D) 小修补（is_on_shift / group_id 清空 / 心跳节流 / 工具 locale / 知识库审批）。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy Core(async) / alembic / pytest(asyncio_mode=auto) / React + react-router-dom / TypeScript / Tailwind。

---

## 关键约定（沿用 M1-M3）

1. 可选筛选 SQL：`(CAST(:p AS TEXT) IS NULL OR col = :p)`。
2. 时间列用 `now_str()`。
3. 新增表/改列：① 加进 `schema.py`；② 独立 alembic 迁移；③ parity 测试通过 + 单 head。
4. 后端测试用 `temp_db_url`/`seeded_db` + `ASGITransport` + `AsyncClient`。
5. 角色 gate：`require_roles(*roles)`；M4 引入 `require_permission(perm_key)` 试点。
6. 写操作审计：`admin_audit.log_admin_action`。
7. 后端单测：`cd server && .venv/bin/python -m pytest tests/xxx.py -v`；ruff：`.venv/bin/ruff check src/<file> tests/<file>`。
8. 前端验证：`pnpm typecheck` + 针对性 `npx eslint`；`max-lines-per-function` ≤80；`PageContainer width="wide"`。
9. git discipline：`main` 分支（用户已同意）；预存 11 modified + 1 untracked 不动；`git -C /Users/sunchenglin/codes/tevau-cs-engine ...` 用绝对路径。
10. commit 中文 + 末尾 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`。

---

## 前置条件（Phase 4 / Theme A 强依赖）

**Theme A（5 个 task）改动 `chat.py`、`useChat.ts`、`chat.ts`、`chatEvents.ts` 这几个 M1-M3 期间是脏文件的源。M4 必须先确认：**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/api/chat.py web/src/api/chat.ts web/src/hooks/useChat.ts web/src/hooks/chatEvents.ts
```

期望：**全部无输出**（用户已把脏改动整理成 commit 或丢弃）。

- 若任一仍脏：**跳过 Phase 4 Theme A 整组**，把它整组留 M5；Phase 1-3 / Theme B/C/D 可独立完成。
- 若全部干净：按本 plan 顺序执行 Phase 1-4。

---

## M1-M3 已交付基线（M4 直接复用）

- 角色 6 个 + `require_roles`；审计 `admin_audit.log_admin_action`；`StaffLayout.tsx` 用 `roles?: string[]`；前端 `api/admin*.ts` 模式。
- M2 工具策略：`tool_policies.is_tool_allowed/is_unmask_allowed`；客服代查端点已接入。
- M2 成本：`daily_token_usage` 加了 `model` 列（旧表）；M3c `daily_token_usage_by_model` 拆表已存在；写入已双写新表；`admin_cost.usage_by_model` 已改读新表。
- M3a：`staff_groups`、`staff_presence`、`staff_shifts`、`routing_rules` + `conversations.target_group_id` + `routing_rules.route_conversation_now()` helper。
- M3b：`prompt_drafts`（loader DB-first 已生效）、`knowledge_entries`（`lookup_*` 已 DB-first）、`guardrail_rules` + `guardrails.evaluate()` helper、AI 自动调用接 `tool_policies.is_tool_allowed("ai")`。
- M3c：`role_permissions` + `rbac.is_permitted/list_matrix`、`report_definitions` + 报表执行引擎、RBAC 前端可编辑。

---

## 文件结构总览

**后端新增**：
- `server/src/ai_engine/auth/permission_dep.py` — `require_permission(perm_key)` 依赖
- `server/src/ai_engine/persistence/shifts_query.py` — `is_on_shift(staff_id, when)` 查询

**后端修改**：
- `server/src/ai_engine/persistence/schema.py` — `knowledge_entries.status` CHECK 加 `pending_review`；其它表不动
- `server/src/ai_engine/auth/staff_session.py` — 加 `require_permission`（或新文件 `permission_dep.py`）
- `server/src/ai_engine/persistence/admin_cost.py` — 删 `daily_token_usage` 旧表读取分支（确认非脏）
- `server/src/ai_engine/governance/token_budget.py` — `_record` 删旧表 INSERT，只双写策略改为单写新表（确认非脏）
- `server/src/ai_engine/persistence/reports.py` — `_METRIC_OPS` 加 `pct` / `growth`；CSV 改流式
- `server/src/ai_engine/persistence/guardrails.py` — `evaluate` 加 `scope_toggle` 分支
- `server/src/ai_engine/persistence/staff_presence.py` — `list_active` 可选 `on_shift_only` 过滤
- `server/src/ai_engine/persistence/staff.py` — `set_staff_group` 接受 0 → 视为 None
- `server/src/ai_engine/api/admin_reports.py` — CSV 改 `StreamingResponse` 分片
- `server/src/ai_engine/api/agent_ratings.py` — `eligibility` 已就绪；M4 不动
- `server/src/ai_engine/api/admin_staff.py` — `StaffPatchIn.group_id` 接受 0 表示清空
- `server/src/ai_engine/api/staff_conversations.py` — 列表接受 `my_group_only` 参数；按当前 staff group_id 过滤（**确认非脏**）
- `server/src/ai_engine/agent/runtime.py` — AI 自动调用前查 `is_unmask_allowed("ai", tool)`（**确认非脏**）
- `server/src/ai_engine/agent/tools/lookup_api_doc.py` / `lookup_error_code.py` — 工具签名加 `locale` 参数
- `server/src/ai_engine/api/admin_knowledge.py` — publish 改为 `pending_review → published` 两步
- **`server/src/ai_engine/api/chat.py`** — Theme A：用户消息入口加 `guardrails.evaluate`、转人工时调 `route_conversation_now`（**前置：用户整理后才动**）

**前端新增**：
- `web/src/hooks/useDynamicMenu.ts` — 从后端 fetch RBAC 矩阵 + 过滤菜单
- `web/src/components/AgentRatingPromptToast.tsx` — Theme A：被动满意度提示（依赖 useChat.ts 整理）

**前端修改**：
- `web/src/components/StaffLayout.tsx` — `useNavItems` 改用 `useDynamicMenu`
- `web/src/api/adminStaff.ts` — `patchStaff` 类型 `group_id` 允许 `0`（前端语义）
- `web/src/routes/admin/StaffAccountsRoute.tsx` — 分组下拉允许选 "—" 清空
- `web/src/hooks/useStaffPresenceHeartbeat.ts` — 心跳间隔从 60s 改 300s + 窗口同步加大
- `web/src/routes/admin/RoutingRulesRoute.tsx` — 提示文字去掉 "M3a 接入点见任务 4.5"，已接入
- `web/src/routes/admin/ReportsRoute.tsx` — filter 输入加类型 hint
- `web/src/api/userAgentRating.ts` — 已就绪；M4 不动

---

# Phase 1 — Theme B 菜单与权限动态化

## Task 1.1: require_permission 依赖

**Files:**
- Create: `server/src/ai_engine/auth/permission_dep.py`
- Test: `server/tests/test_require_permission.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_require_permission.py
import pytest
from fastapi import HTTPException

from ai_engine.auth.permission_dep import require_permission


async def test_allows_when_permitted(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    await rbac.upsert_many("AD1", [
        {"role": "agent", "permission_key": "test.feature", "allowed": 1},
    ])
    dep = require_permission("test.feature")
    out = await dep({"role": "agent"})
    assert out["role"] == "agent"


async def test_rejects_when_no_permission(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    dep = require_permission("test.feature")
    with pytest.raises(HTTPException) as e:
        await dep({"role": "agent"})
    assert e.value.status_code == 403


async def test_admin_default_has_all(temp_db_url):
    from ai_engine.persistence import rbac
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()
    dep = require_permission("admin.dashboard")
    out = await dep({"role": "admin"})
    assert out["role"] == "admin"
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_require_permission.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/auth/permission_dep.py
"""动态权限依赖：通过 perm_key 查 role_permissions 矩阵决定放行。

与 require_roles 的关系：require_roles 是按角色集合判定，require_permission 是按权限位判定。
M4 试点用于新端点；旧端点保持 require_roles 不变。
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException

from ai_engine.auth.staff_session import require_staff
from ai_engine.persistence import rbac


def require_permission(perm_key: str) -> Callable[..., Any]:
    """生成依赖：检查当前 staff.role 是否拥有 perm_key 权限。"""

    async def _dep(staff: dict[str, Any] = Depends(require_staff)) -> dict[str, Any]:
        role = str(staff.get("role", ""))
        if not await rbac.is_permitted(role, perm_key):
            raise HTTPException(403, f"missing permission: {perm_key}")
        return staff

    return _dep
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_require_permission.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/auth/permission_dep.py tests/test_require_permission.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/auth/permission_dep.py server/tests/test_require_permission.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): require_permission 依赖（按 RBAC 矩阵动态判定）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.2: StaffLayout 菜单从 RBAC 矩阵 fetch

**Files:**
- Create: `web/src/hooks/useDynamicMenu.ts`
- Modify: `web/src/components/StaffLayout.tsx` — `useNavItems` 改为用 dynamic menu hook

设计：fetch 失败时回退到 hardcoded roles（M3a 的 `roles?: string[]`），保证菜单永远可见。

- [ ] **Step 1: 新建 hook**

```typescript
// web/src/hooks/useDynamicMenu.ts
import { useEffect, useState } from "react";

import { getMatrix, type RbacMatrix } from "../api/adminRbac";

import { useStaffSession } from "./useStaffSession";

/** fetch RBAC 矩阵；任何错误（包括非 admin 403）静默回退到 null，由消费方走静态 roles 兜底。 */
export function useDynamicMenu(): { matrix: RbacMatrix | null; loading: boolean } {
  const { token, role } = useStaffSession();
  const [matrix, setMatrix] = useState<RbacMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!token) { setMatrix(null); setLoading(false); return; }
    let cancelled = false;
    // 仅 admin 能读矩阵；其它角色 fetch 会 403，静默走 null（消费方回退 hardcoded roles）
    if (role !== "admin") { setLoading(false); return; }
    setLoading(true);
    getMatrix(token)
      .then((m) => { if (!cancelled) setMatrix(m); })
      .catch(() => { if (!cancelled) setMatrix(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, role]);
  return { matrix, loading };
}
```

- [ ] **Step 2: 改 StaffLayout 加 path→perm_key 映射 + 用 hook**

读 `web/src/components/StaffLayout.tsx`。在 NAV_ITEMS 之后追加映射表（path → permission_key）：
```typescript
const PATH_TO_PERM: Record<string, string> = {
  "/admin/dashboard": "admin.dashboard",
  "/admin/staff": "admin.staff",
  "/admin/performance": "admin.performance",
  "/admin/qa": "admin.qa",
  "/admin/sla": "admin.sla",
  "/admin/tools": "admin.tools",
  "/admin/cost": "admin.cost",
  "/admin/audit": "admin.audit",
  "/admin/prompts": "admin.prompts",
  "/admin/rbac": "admin.rbac",
  "/admin/staff-groups": "admin.staff_groups",
  "/admin/presence": "admin.presence",
  "/admin/shifts": "admin.shifts",
  "/admin/routing": "admin.routing",
  "/admin/prompt-editor": "admin.prompt_editor",
  "/admin/knowledge": "admin.knowledge",
  "/admin/guardrails": "admin.guardrails",
  "/admin/reports": "admin.reports",
};
```
顶部 import 增加：
```typescript
import { useDynamicMenu } from "../hooks/useDynamicMenu";
```
改 `useNavItems`：
```typescript
function useNavItems() {
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();
  return NAV_ITEMS.filter((i) => {
    // 仅管理后台菜单(/admin/* 且有 PATH_TO_PERM 映射)走动态矩阵；
    // 工作台等 /staff/* 仍按 hardcoded roles（缺省 = 所有登录用户）。
    const permKey = PATH_TO_PERM[i.to];
    if (matrix && permKey && role) {
      return matrix.matrix[role]?.[permKey] === true;
    }
    // 回退：hardcoded roles
    return !i.roles || (role != null && i.roles.includes(role));
  });
}
```

- [ ] **Step 3: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/hooks/useDynamicMenu.ts src/components/StaffLayout.tsx` → 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/hooks/useDynamicMenu.ts web/src/components/StaffLayout.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 菜单可见性按 RBAC 矩阵动态过滤（admin fetch 矩阵；其它角色回退 hardcoded）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 1.3: 客服列表按 my_group_only 过滤接入

**Files:**
- Modify: `server/src/ai_engine/api/staff_conversations.py`（**先确认非脏**）
- Test: `server/tests/test_my_group_filter.py`

- [ ] **Step 1: 确认非脏**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/api/staff_conversations.py` → 无输出。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_my_group_filter.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence import admin_staff_groups
    from ai_engine.persistence.staff import create_staff, set_staff_group

    g1 = await admin_staff_groups.create_group("证券组", None)
    await create_staff("AG1", "客服1", "agent", "x")
    await set_staff_group("AG1", g1)
    # 会话 A：target_group_id = g1（命中组）
    await db.execute(
        f"INSERT INTO conversations(id, user_type, subject_id, mode, target_group_id, "
        f"created_at) VALUES (1, 'b', 'BU1', 'human_pending', {g1}, '2026-06-01 00:00:00')"
    )
    # 会话 B：target_group_id = NULL（无定向）
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (2, 'b', 'BU2', 'human_pending', '2026-06-01 00:00:00')"
    )
    # 会话 C：target_group_id = 9999（别的组，AG1 看不到）
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, target_group_id, "
        "created_at) VALUES (3, 'b', 'BU3', 'human_pending', 9999, '2026-06-01 00:00:00')"
    )
    yield {"ag": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_my_group_only_filters(env):
    """my_group_only=true 时 AG1 只能看到本组(A)和无定向(B)，看不到 C。"""
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get(
            "/staff/api/v1/conversations?my_group_only=true",
            headers=_h(env["ag"]),
        )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json().get("conversations", r.json())}
    assert 1 in ids and 2 in ids
    assert 3 not in ids


async def test_without_filter_sees_all(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get(
            "/staff/api/v1/conversations",
            headers=_h(env["ag"]),
        )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json().get("conversations", r.json())}
    assert {1, 2, 3} <= ids
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_my_group_filter.py -v`
Expected: `test_my_group_only_filters` FAIL（参数尚未实现）。

- [ ] **Step 4: 改 staff_conversations.py**

读 staff_conversations.py 定位 `GET /staff/api/v1/conversations` 列表端点：
```
grep -n "@router.get.*staff/api/v1/conversations" server/src/ai_engine/api/staff_conversations.py
```
在该端点签名加：`my_group_only: bool = Query(default=False)`（顶部已 import Query；如未 import 加上）。

在查询逻辑里：
```python
my_group: int | None = None
if my_group_only:
    from ai_engine.persistence.staff import get_staff
    staff_id = str(staff.get("sub", ""))
    me = await get_staff(staff_id) if staff_id else None
    my_group = int(me["group_id"]) if me and me.get("group_id") is not None else None

# 在原 SQL WHERE 加：
if my_group_only:
    where_clauses.append(
        "(target_group_id IS NULL OR "
        "(CAST(:mg AS TEXT) IS NOT NULL AND target_group_id = :mg))"
    )
    binds["mg"] = my_group
```
注意：`get_staff` 现在返回 `staff_id/display_name/role/active`——M3a 已改 `list_staff` 加 `group_id/skills`，但 `get_staff` 未改。**本 task 先扩 `get_staff` 一并返回 `group_id`**：在 `server/src/ai_engine/persistence/staff.py` 的 `get_staff` 把 `SELECT staff_id, display_name, role, active` 改为 `SELECT staff_id, display_name, role, active, group_id`。

- [ ] **Step 5: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_my_group_filter.py tests/test_admin_staff_dao.py -v` (既有不退化)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/staff.py src/ai_engine/api/staff_conversations.py tests/test_my_group_filter.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/staff.py server/src/ai_engine/api/staff_conversations.py server/tests/test_my_group_filter.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 客服列表 my_group_only 过滤接入（按当前 staff group_id）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 2 — Theme C 成本/报表完善

## Task 2.1: daily_token_usage 旧表删除 + 写入路径切换

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py` — 删除 `daily_token_usage` 表定义
- Modify: `server/src/ai_engine/governance/token_budget.py` — `_record` 删旧表 INSERT，只写新表（确认非脏）
- Modify: `server/src/ai_engine/persistence/admin_cost.py` — 若仍有 fallback 读旧表的分支，删除
- Create: 新 alembic 迁移（drop_table daily_token_usage）

- [ ] **Step 1: 确认旧表读取处全部已切**

Run: `cd server && grep -rn "FROM daily_token_usage[^_]\|INTO daily_token_usage[^_]" src/ tests/`
Expected: 仅 `daily_token_usage_by_model` 命中；若仍有读 `daily_token_usage` 的：先把那些处切到 `daily_token_usage_by_model` 再继续本 task。
Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/governance/token_budget.py server/src/ai_engine/persistence/admin_cost.py`
Expected: 无输出。

- [ ] **Step 2: 写失败测试**

```python
# server/tests/test_token_budget_only_new_table.py
async def test_record_writes_only_new_table(temp_db_url):
    """M4: 旧表已删；写入只落新表。"""
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence import db
    from ai_engine.persistence.db import init_db
    await init_db()
    await check_and_record("b", "BU1", 100, 50, model="claude-sonnet-4-6")
    # 新表有
    row = await db.fetch_one(
        "SELECT input_tokens FROM daily_token_usage_by_model "
        "WHERE subject_id='BU1' AND user_type='b' AND model='claude-sonnet-4-6'"
    )
    assert row is not None
    # 旧表不应存在
    import pytest
    from sqlalchemy.exc import OperationalError, ProgrammingError
    with pytest.raises((OperationalError, ProgrammingError)):
        await db.fetch_one(
            "SELECT input_tokens FROM daily_token_usage WHERE subject_id='BU1'"
        )
```

- [ ] **Step 3: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_token_budget_only_new_table.py -v` → 旧表仍存在，最后一个断言失败。

- [ ] **Step 4: 改 schema.py + token_budget.py**

`schema.py`：定位 `daily_token_usage = Table(...)` 整段删除（含 `Column("model", ...)`）；保留 `daily_token_usage_by_model`。

`token_budget.py`：定位 `_record` 函数，把对 `INSERT INTO daily_token_usage(...)...ON CONFLICT...` 那块删除，只保留 `INSERT INTO daily_token_usage_by_model(...)...ON CONFLICT(subject_id, user_type, date, model) DO UPDATE...`。
另外 `_get_used / is_exhausted` 等仍读旧表的，把 SELECT 改为：
```python
"SELECT COALESCE(SUM(input_tokens), 0) AS in_t, COALESCE(SUM(output_tokens), 0) AS out_t "
"FROM daily_token_usage_by_model "
"WHERE subject_id = :sid AND user_type = :ut AND date = :day"
```
（聚合各 model 行得当日总额。）

- [ ] **Step 5: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "drop_daily_token_usage"`
编辑生成文件：
```python
def upgrade() -> None:
    op.drop_table("daily_token_usage")


def downgrade() -> None:
    op.create_table(
        "daily_token_usage",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("user_type", sa.String(8), primary_key=True),
        sa.Column("date", sa.String(16), primary_key=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(32), nullable=True),
    )
```

- [ ] **Step 6: parity + 全套验证 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py tests/test_token_budget_only_new_table.py tests/test_token_budget.py tests/test_token_budget_model.py tests/test_admin_cost_dao.py tests/test_admin_cost_api.py -v`
Expected: 全 pass（旧表测试如 `test_token_budget` 里依赖 daily_token_usage SELECT 的需同步迁，按现状判断）。
Run: `cd server && .venv/bin/python -m alembic heads` (单 head)
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/src/ai_engine/governance/token_budget.py server/src/ai_engine/persistence/admin_cost.py server/migrations/versions/ server/tests/test_token_budget_only_new_table.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 删除 daily_token_usage 旧表 + token 写入只落新表" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.2: 报表 metrics 扩 derived（min/max 已支持；加百分位 / growth）

**Files:**
- Modify: `server/src/ai_engine/persistence/reports.py` — `_METRIC_OPS` 加 `"pct50" "pct95"`；`execute()` 把 pctNN 转 SQL（SQLite/PG 都支持 `PERCENTILE_DISC` 在 PG，SQLite 用 `(SELECT value FROM ...)` 模拟略复杂 → 改用 `MIN/MAX/AVG/COUNT/SUM` 为 M4 最小集，把 pct 留 M5）
- Test: `server/tests/test_reports_growth.py`

更务实的范围调整：**百分位跨库实现复杂**，M4 只扩 `growth`（值=同期对比 N 期：`(current - prev) / prev`），需要数据格式跨期聚合，工程量也大。

**收敛：本 task 只做"derived metric: ratio"**——给 metrics 加一个新 op `ratio`，意思是"两列相除 × 100"。如：`{"op":"ratio","col":"upvote","over":"upvote+downvote","alias":"upvote_rate"}`。仍是单查询、白名单受控。

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_reports_ratio.py
from ai_engine.persistence import db, reports


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_ratio_metric(temp_db_url):
    await _init(temp_db_url)
    await db.execute(
        "INSERT INTO message_feedback(conversation_id, message_id, rating, "
        "subject_id, user_type, created_at) VALUES "
        "(1, 1, 'up', 'u1', 'c', '2026-06-01 00:00:00'), "
        "(2, 1, 'up', 'u1', 'c', '2026-06-01 00:00:00'), "
        "(3, 1, 'down', 'u1', 'c', '2026-06-01 00:00:00')"
    )
    # 注：reports._SOURCES 当前不含 message_feedback；本 task 一并加入
    result = await reports.execute(
        source="message_feedback",
        dims=["user_type"],
        filters=[],
        metrics=[
            {"op": "count", "col": "*", "alias": "n"},
            {"op": "count_if", "col": "rating", "match": "up", "alias": "n_up"},
        ],
    )
    row = next(r for r in result["rows"] if r["user_type"] == "c")
    assert row["n"] == 3
    assert row["n_up"] == 2
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_reports_ratio.py -v`
Expected: FAIL — `count_if` op 不支持 / message_feedback 不在 source 白名单。

- [ ] **Step 3: 改 reports.py**

(a) `_SOURCES` 加 `message_feedback`：
```python
    "message_feedback": {
        "id", "conversation_id", "message_id", "rating",
        "subject_id", "user_type", "created_at",
    },
```

(b) `_METRIC_OPS` 加 `"count_if"`：
```python
_METRIC_OPS = {"count", "sum", "avg", "min", "max", "count_if"}
```

(c) `_validate_metrics` 加 count_if 校验：
```python
def _validate_metrics(source, metrics):
    cols = _SOURCES.get(source, set())
    for m in metrics:
        op = m.get("op", "")
        col = m.get("col", "")
        if op not in _METRIC_OPS:
            raise ValueError(f"unknown metric op: {op}")
        if col != "*" and col not in cols:
            raise ValueError(f"unknown metric col {col}")
        if op == "count_if":
            if "match" not in m or not isinstance(m["match"], (str, int)):
                raise ValueError("count_if requires 'match' value")
```

(d) `execute` 的 SELECT 构造加 `count_if` 分支：
```python
for i, m in enumerate(metrics):
    op = str(m["op"]).upper()
    col = str(m["col"])
    alias = str(m.get("alias", f"{op}_{col}"))
    if not alias.replace("_", "").isalnum():
        raise ValueError(f"invalid alias: {alias}")
    if op == "COUNT_IF":
        bind_key = f"_mv{i}"
        select_parts.append(
            f"SUM(CASE WHEN {col} = :{bind_key} THEN 1 ELSE 0 END) AS {alias}"
        )
        binds[bind_key] = m["match"]
    elif col == "*":
        select_parts.append(f"{op}(*) AS {alias}")
    else:
        select_parts.append(f"{op}({col}) AS {alias}")
```

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_reports_ratio.py tests/test_reports_dao.py tests/test_admin_reports_api.py -v` (新 pass + 既有不退化)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/reports.py tests/test_reports_ratio.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/reports.py server/tests/test_reports_ratio.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 报表 metrics 扩 count_if + 加 message_feedback 数据源" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.3: CSV 流式分片导出

**Files:**
- Modify: `server/src/ai_engine/api/admin_reports.py` — `export_csv` 改为生成器 + StreamingResponse 流式
- Test: `server/tests/test_admin_reports_csv_stream.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_admin_reports_csv_stream.py
"""验证 CSV 导出走流式 chunk（非一次性内存）。"""
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
    # 批量插入 200 行 agent_ratings 模拟"大"报表
    rows = ",".join(
        f"({i}, 'AG{i % 5}', 'u{i}', 'c', {1 + i % 5}, '2026-06-01 00:00:00')"
        for i in range(1, 201)
    )
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        f"rating, created_at) VALUES {rows}"
    )
    yield {"sup": issue_staff_token("SUP1", "supervisor")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_csv_export_streams_all_rows(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r0 = await c.post(
            "/admin/api/v1/reports",
            json={
                "name": "ratings_by_staff",
                "source": "agent_ratings",
                "dims": ["staff_id"],
                "filters": [],
                "metrics": [{"op": "count", "col": "*", "alias": "n"}],
            },
            headers=_h(env["sup"]),
        )
        rid = r0.json()["id"]
        async with c.stream("GET", f"/admin/api/v1/reports/{rid}/export.csv",
                            headers=_h(env["sup"])) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/csv")
            chunks = []
            async for chunk in resp.aiter_text():
                chunks.append(chunk)
    text = "".join(chunks)
    assert "staff_id" in text  # header
    # 5 个 staff 分组（AG0..AG4）+ 1 header = 6 行
    assert text.count("\n") >= 5
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_reports_csv_stream.py -v`
Expected: 当前实现 OK 也能通过（一次性把 200 行字符串塞进 iter([buf.getvalue()])）。流式重写的价值是不在内存 buffer 一次性所有行。验证流式真正分片需要在 patch 后用更精细的 unit test 检查生成器行为——本 task 验证"流式不退化既有功能"即可。

如初次测试就 pass：仍执行 Step 3 重写（让实现真正分片，便于大数据集），然后再跑确保不退化。

- [ ] **Step 3: 改 admin_reports.py 改流式生成器**

读 `server/src/ai_engine/api/admin_reports.py` 的 `export_csv`，改为：
```python
import io
import csv

from fastapi.responses import StreamingResponse


@router.get("/admin/api/v1/reports/{report_id}/export.csv")
async def export_csv(report_id: int, staff: dict[str, Any] = Depends(_view)) -> StreamingResponse:
    result = await _run(report_id)
    rows = result["rows"]
    fieldnames = list(rows[0].keys()) if rows else []

    async def _gen():
        # header
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        yield buf.getvalue()
        # 每行单独 yield，避免一次性内存堆积
        for row in rows:
            buf2 = io.StringIO()
            csv.DictWriter(buf2, fieldnames=fieldnames).writerow(row)
            yield buf2.getvalue()

    return StreamingResponse(
        _gen(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.csv"'},
    )
```

- [ ] **Step 4: 跑测试 PASS + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_admin_reports_csv_stream.py tests/test_admin_reports_api.py -v` (新 + 既有 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/admin_reports.py tests/test_admin_reports_csv_stream.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/admin_reports.py server/tests/test_admin_reports_csv_stream.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 报表 CSV 导出改流式（生成器按行 yield）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2.4: 报表 filter UI 加类型提示

**Files:**
- Modify: `web/src/routes/admin/ReportsRoute.tsx`

设计：filter 数组当前由用户写 JSON。本 task 加一个"列名 → 推荐类型"提示文案（不改数据模型，只改 hint UI）。

- [ ] **Step 1: 改 ReportsRoute**

读 ReportsRoute.tsx。在 `ReportForm` 组件下面加一段帮助文本：
```tsx
<p className="px-page pb-block-sm text-footnote text-ink-tertiary">
  filters 示例：<code>[{"{"}"col":"created_at","op":">=","val":"2026-06-01 00:00:00"{"}"}]</code>
  字符串/日期请用引号；数字直接写。op 仅支持 = != &gt; &gt;= &lt; &lt;= LIKE。
</p>
```
此 hint 加在 metrics textarea 下方。

- [ ] **Step 2: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/routes/admin/ReportsRoute.tsx` → 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/routes/admin/ReportsRoute.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 报表表单加 filter 语法提示" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 3 — Theme D 小修补

## Task 3.1: is_on_shift helper + 排班过滤显示

**Files:**
- Create: `server/src/ai_engine/persistence/shifts_query.py`
- Modify: `server/src/ai_engine/persistence/staff_presence.py` — `list_active` 加 `on_shift_only` 参数
- Test: `server/tests/test_is_on_shift.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_is_on_shift.py
from ai_engine.persistence import shifts_query


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_on_shift_within_range(temp_db_url):
    from ai_engine.persistence import admin_shifts
    await _init(temp_db_url)
    await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    assert await shifts_query.is_on_shift("AG1", "2026-06-01 12:00:00") is True


async def test_off_shift_outside_range(temp_db_url):
    from ai_engine.persistence import admin_shifts
    await _init(temp_db_url)
    await admin_shifts.create_shift("AG1", "2026-06-01 09:00:00", "2026-06-01 18:00:00")
    assert await shifts_query.is_on_shift("AG1", "2026-06-01 20:00:00") is False


async def test_no_shift_returns_false(temp_db_url):
    await _init(temp_db_url)
    assert await shifts_query.is_on_shift("NOPE", "2026-06-01 12:00:00") is False
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_is_on_shift.py -v` → ModuleNotFoundError。

- [ ] **Step 3: 实现**

```python
# server/src/ai_engine/persistence/shifts_query.py
"""排班"在班"判定：UTC 时间点是否落在该 staff 的任一排班区间。"""

from ai_engine.persistence import db


async def is_on_shift(staff_id: str, when_utc: str) -> bool:
    row = await db.fetch_one(
        "SELECT 1 AS ok FROM staff_shifts "
        "WHERE staff_id = :sid AND start_at <= :w AND end_at >= :w "
        "LIMIT 1",
        {"sid": staff_id, "w": when_utc},
    )
    return row is not None
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_is_on_shift.py -v` (3 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/shifts_query.py tests/test_is_on_shift.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/shifts_query.py server/tests/test_is_on_shift.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): is_on_shift helper（判定时间点是否在某 staff 排班内）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.2: PATCH staff group_id=0 清空语义

**Files:**
- Modify: `server/src/ai_engine/persistence/staff.py` — `set_staff_group(staff_id, group_id)` 把 `0` 视为 `None`
- Modify: `web/src/api/adminStaff.ts` — `patchStaff` 类型注释保持现状（接受 number）；前端 StaffAccountsRoute 已用 0=—
- Modify: `web/src/routes/admin/StaffAccountsRoute.tsx` — 解除"v === 0 return"的拦截，允许保存清空
- Test: `server/tests/test_staff_group_clear.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_staff_group_clear.py
from ai_engine.persistence import admin_staff_groups, staff as staff_mod


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_set_group_zero_clears(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("g", None)
    await staff_mod.create_staff("AG1", "x", "agent", "x")
    await staff_mod.set_staff_group("AG1", gid)
    # M4: 传 0 视为 None
    await staff_mod.set_staff_group("AG1", 0)
    row = next(r for r in await staff_mod.list_staff() if r["staff_id"] == "AG1")
    assert row["group_id"] is None
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_group_clear.py -v` → 当前实现把 0 写成 0（不是 NULL）。

- [ ] **Step 3: 改 set_staff_group**

读 `server/src/ai_engine/persistence/staff.py` 的 `set_staff_group`：
```python
async def set_staff_group(staff_id: str, group_id: int | None) -> None:
    # M4: 0 视为清空（等价 None），对齐前端 "—" 选项
    normalized = None if (group_id is None or int(group_id) == 0) else int(group_id)
    await db.execute(
        "UPDATE staff SET group_id = :g WHERE staff_id = :sid",
        {"g": normalized, "sid": staff_id},
    )
```

- [ ] **Step 4: 改前端 StaffAccountsRoute**

读 `web/src/routes/admin/StaffAccountsRoute.tsx`。定位 `onChangeGroup`：
```typescript
  async function onChangeGroup(staffId: string, groupId: number) {
    if (!token) return;  // 不再拒绝 0
    try { await patchStaff(token, staffId, { group_id: groupId }); onRefresh(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
```
（删去 `if (groupId === 0) return;` 这行。）

- [ ] **Step 5: 跑测试 + 前端验证 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_group_clear.py tests/test_admin_staff_groups_dao.py -v`
Run: `cd web && pnpm typecheck && npx eslint src/routes/admin/StaffAccountsRoute.tsx`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/staff.py web/src/routes/admin/StaffAccountsRoute.tsx server/tests/test_staff_group_clear.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 分组下拉支持清空（前端选 — 对应 group_id=0 → null）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.3: 心跳节流（60s → 300s）

**Files:**
- Modify: `web/src/hooks/useStaffPresenceHeartbeat.ts`

- [ ] **Step 1: 改 INTERVAL_MS**

读 hook，把 `const INTERVAL_MS = 60_000;` 改为 `const INTERVAL_MS = 300_000;`。

> 注：后端 `list_active(window_seconds=300)` 当前窗口 300s。心跳间隔 = 窗口长度刚好——一次错过即 offline。把后端窗口拉到 360s 给抖动空间：定位 `staff_presence.py` 的 `list_active` 默认参数，把 300 改 360，相应 API `admin_list` 调用处同步。

- [ ] **Step 2: 改后端窗口**

读 `server/src/ai_engine/persistence/staff_presence.py`：
```python
async def list_active(window_seconds: int = 360) -> list[dict[str, Any]]:
```
读 `server/src/ai_engine/api/staff_presence.py` 的 `admin_list`：
```python
    active = await staff_presence.list_active(window_seconds=360)
```

- [ ] **Step 3: 跑既有测试 + 验证 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_staff_presence_dao.py tests/test_staff_presence_api.py -v`（既有测试用 `window_seconds=300` 显式参数，仍 pass；默认值变了不影响）
Run: `cd web && pnpm typecheck && npx eslint src/hooks/useStaffPresenceHeartbeat.ts`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/hooks/useStaffPresenceHeartbeat.ts server/src/ai_engine/persistence/staff_presence.py server/src/ai_engine/api/staff_presence.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 心跳节流 60s → 300s + 后端窗口 300s → 360s 留抖动空间" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.4: lookup_* 工具加 locale 参数

**Files:**
- Modify: `server/src/ai_engine/agent/tools/lookup_api_doc.py`（确认非脏）
- Modify: `server/src/ai_engine/agent/tools/lookup_error_code.py`（确认非脏）
- Test: `server/tests/test_lookup_locale.py`

- [ ] **Step 1: 确认非脏 + 写失败测试**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/agent/tools/lookup_api_doc.py server/src/ai_engine/agent/tools/lookup_error_code.py`
Expected: 无输出。

```python
# server/tests/test_lookup_locale.py
async def test_lookup_error_code_uses_locale_en(temp_db_url):
    from ai_engine.persistence import knowledge
    from ai_engine.persistence.db import init_db
    await init_db()
    eid_zh = await knowledge.upsert_entry(
        type_="error_code", key="E2000", title="中文标题",
        content="中文说明", locale="zh", created_by="EN1",
    )
    await knowledge.publish(eid_zh)
    eid_en = await knowledge.upsert_entry(
        type_="error_code", key="E2000", title="English title",
        content="English content", locale="en", created_by="EN1",
    )
    await knowledge.publish(eid_en)
    from ai_engine.agent.tools.lookup_error_code import _handler
    result_en = await _handler(code="E2000", locale="en")
    assert "English content" in str(result_en)
    result_zh = await _handler(code="E2000")
    assert "中文说明" in str(result_zh)
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_lookup_locale.py -v`
Expected: en 分支当前实现读 locale="zh"（默认）→ 拿到中文，断言 fail。

- [ ] **Step 3: 改 lookup_error_code.py / lookup_api_doc.py 处理 locale**

定位两个工具的 `_handler`，确保签名 `async def _handler(code: str, locale: str = "zh", **kw)` / `async def _handler(path: str, locale: str = "zh", **kw)`，并把 DB 查询用 `locale` 参数（M3b 时已经写好；本 task 检查 `input_schema` 字段把 `locale` 加入工具描述，让 AI 可以传该参数）。

Tool schema 改造（每个工具的 `Tool(input_schema=...)`）：
```python
input_schema={
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "错误码"},
        "locale": {"type": "string", "enum": ["zh", "en"], "default": "zh"},
    },
    "required": ["code"],
}
```
(lookup_api_doc 同理，`code` 改为 `path`。)

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_lookup_locale.py tests/test_lookup_db_first.py tests/test_lookup_api_doc.py -v`
Run: `cd server && .venv/bin/ruff check src/ai_engine/agent/tools/lookup_error_code.py src/ai_engine/agent/tools/lookup_api_doc.py tests/test_lookup_locale.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/agent/tools/lookup_error_code.py server/src/ai_engine/agent/tools/lookup_api_doc.py server/tests/test_lookup_locale.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): lookup_* 工具 input_schema 加 locale 让 AI 可指定语言" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.5: 知识库加 pending_review 中间态

**Files:**
- Modify: `server/src/ai_engine/persistence/schema.py` — `knowledge_entries.status` CHECK 加 `pending_review`
- Create: 新 alembic 迁移 (batch_alter_table 重建 CHECK)
- Modify: `server/src/ai_engine/persistence/knowledge.py` — 新增 `submit_for_review(eid)` + `publish` 只接受 `pending_review → published`
- Modify: `server/src/ai_engine/api/admin_knowledge.py` — 加 `POST /admin/api/v1/knowledge/{id}/submit-for-review`
- Test: `server/tests/test_knowledge_workflow.py`

- [ ] **Step 1: 改 schema CHECK**

读 `schema.py`，定位 `knowledge_entries` 的 CheckConstraint：
```python
    CheckConstraint("status IN ('draft','pending_review','published')", name="ck_knowledge_status"),
```

- [ ] **Step 2: 建迁移**

Run: `cd server && .venv/bin/python -m alembic revision -m "knowledge_pending_review"`
编辑：
```python
def upgrade() -> None:
    with op.batch_alter_table("knowledge_entries", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_knowledge_status",
            "status IN ('draft','pending_review','published')",
        )


def downgrade() -> None:
    with op.batch_alter_table("knowledge_entries", recreate="always") as batch_op:
        batch_op.create_check_constraint(
            "ck_knowledge_status", "status IN ('draft','published')"
        )
```

- [ ] **Step 3: 改 persistence**

读 `knowledge.py`：
```python
async def submit_for_review(entry_id: int) -> None:
    await db.execute(
        "UPDATE knowledge_entries SET status = 'pending_review', updated_at = :now "
        "WHERE id = :id AND status = 'draft'",
        {"now": now_str(), "id": int(entry_id)},
    )


async def publish(entry_id: int) -> None:
    # M4: 只允许 pending_review → published（强制走审核流）
    await db.execute(
        "UPDATE knowledge_entries SET status = 'published', updated_at = :now "
        "WHERE id = :id AND status = 'pending_review'",
        {"now": now_str(), "id": int(entry_id)},
    )
```

- [ ] **Step 4: 改 API**

读 `admin_knowledge.py`，加：
```python
@router.post("/admin/api/v1/knowledge/{entry_id}/submit-for-review")
async def submit_for_review(
    entry_id: int, staff: dict[str, Any] = Depends(_sup)
) -> dict[str, Any]:
    await knowledge.submit_for_review(entry_id)
    await admin_audit.log_admin_action(
        actor=str(staff.get("sub", "unknown")), action="knowledge.submit_for_review",
        target_type="knowledge_entry", target_id=str(entry_id),
    )
    return {"ok": True}
```

- [ ] **Step 5: 写失败测试 + 跑通**

```python
# server/tests/test_knowledge_workflow.py
from ai_engine.persistence import knowledge


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_publish_requires_review_first(temp_db_url):
    await _init(temp_db_url)
    eid = await knowledge.upsert_entry(
        type_="faq", key="x", title="t", content="c", locale="zh", created_by="EN1",
    )
    # draft → publish 不应直接生效（status 仍 draft）
    await knowledge.publish(eid)
    row = await knowledge.get_published(type_="faq", key="x", locale="zh")
    assert row is None  # 未发布
    # 走流程
    await knowledge.submit_for_review(eid)
    await knowledge.publish(eid)
    row = await knowledge.get_published(type_="faq", key="x", locale="zh")
    assert row is not None
```

Run: `cd server && .venv/bin/python -m pytest tests/test_alembic_migrations.py tests/test_knowledge_workflow.py tests/test_knowledge_dao.py tests/test_admin_knowledge_api.py -v`

注意：M3b 的既有测试 `test_create_publish_list` 和 `test_create_publish_get` 直接 `draft → publish` 会被本 task 改 break。**修复策略**：在那些测试的 publish 前加一次 `submit_for_review` 调用——属于既有测试同步更新，不算退化：
```python
# 既有 test_create_publish_get 改：
await knowledge.publish(eid)
# 改为：
await knowledge.submit_for_review(eid)
await knowledge.publish(eid)
```
同理 API 测试 `pub = await c.post(.../publish)` 前加一次 `await c.post(.../submit-for-review)`。

- [ ] **Step 6: Commit**

```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/schema.py server/migrations/versions/ server/src/ai_engine/persistence/knowledge.py server/src/ai_engine/api/admin_knowledge.py server/tests/test_knowledge_workflow.py server/tests/test_knowledge_dao.py server/tests/test_admin_knowledge_api.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): 知识库加 pending_review 中间态（强制 draft → review → published）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3.6: scope_toggle 在 guardrails.evaluate 中处理

**Files:**
- Modify: `server/src/ai_engine/persistence/guardrails.py` — `evaluate` 加 scope_toggle 分支
- Test: 扩展 `server/tests/test_guardrails_dao.py`

设计：scope_toggle 规则的 `pattern` = "scope 名"（如 `"securities"`）。语义："当前业务范围是否启用此 scope"——本里程碑实现为"任何 user_type 进入时若该 scope 已禁用则 block"。简化：M4 把 `scope_toggle` 的语义定为"全局禁用某 scope"，pattern 同时记录 scope 名 + action=block 表示该 scope 全禁。`evaluate` 检测：若有 active `scope_toggle` 规则，按 action 返回。

- [ ] **Step 1: 加测试**

在 `tests/test_guardrails_dao.py` 末尾追加：
```python
async def test_scope_toggle_blocks(temp_db_url):
    from ai_engine.persistence import guardrails
    await _init(temp_db_url)
    await guardrails.create_rule("scope_toggle", "securities", "block", "EN1")
    result = await guardrails.evaluate("USER1", "c", "任何文字")
    assert result == ("block", "scope_toggle:securities")
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_guardrails_dao.py::test_scope_toggle_blocks -v` → FAIL（当前 evaluate 跳过 scope_toggle 类型）。

- [ ] **Step 3: 改 evaluate**

读 `guardrails.py` 的 `evaluate`：
```python
async def evaluate(
    subject_id: str, user_type: str, text: str
) -> tuple[str, str | None]:
    for rule in await _active_rules():
        t = str(rule["type"])
        pat = str(rule["pattern"])
        action = str(rule["action"])
        if t == "blocklist" and pat == subject_id:
            return action, f"blocklist:{pat}"
        if t == "sensitive_word" and pat in text:
            return action, f"sensitive_word:{pat}"
        if t == "scope_toggle":
            # M4: scope 全局禁用——任何会话进入都按 action 处理
            return action, f"scope_toggle:{pat}"
    return "allow", None
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_guardrails_dao.py -v` (5 pass)
Run: `cd server && .venv/bin/ruff check src/ai_engine/persistence/guardrails.py tests/test_guardrails_dao.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/persistence/guardrails.py server/tests/test_guardrails_dao.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): guardrails.evaluate 加 scope_toggle 分支（全局禁用某业务范围）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# Phase 4 — Theme A chat.py 整理后的自动接入（前置依赖）

**前置检查（每个 Theme A task 第一步都要做）**：
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine status --short server/src/ai_engine/api/chat.py web/src/api/chat.ts web/src/hooks/useChat.ts web/src/hooks/chatEvents.ts
```
Expected: 无输出（用户已整理）。若任一仍脏 → BLOCKED 报告，本 Phase 整组跳过。

## Task 4.1: chat.py 转人工时自动调 route_conversation_now

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`（**前置**：非脏）
- Test: `server/tests/test_chat_auto_routing.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_chat_auto_routing.py
"""验证 chat.py 转人工时自动写 target_group_id。"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.persistence import db, routing_rules
    routing_rules.invalidate_cache()
    # 一条路由规则：keyword "卡片" → group 7
    await routing_rules.create_rule("keyword", "卡片", target_group_id=7, priority=10)
    # 一通会话 + 一条 user 消息含"卡片"
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'b', 'BU1', 'ai', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, status, created_at) "
        "VALUES (1, 'user', '我想问卡片申请', 'done', '2026-06-01 00:00:01')"
    )
    yield {}
    routing_rules.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


async def test_handoff_writes_target_group(env):
    """触发转人工后 target_group_id 应被写入。

    触发方式按 chat.py 现有约定：可能是 POST /api/v1/conversations/{id}/handoff
    或者 mode_change 内部调用。本测试用最小信号：直接调用 chat.py 的转人工内部函数。
    若 chat.py 转人工是 endpoint，按实际路径调用；否则适配。
    """
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        # 假设转人工端点为 POST /api/v1/conversations/{id}/handoff（按 chat.py 实际调整）
        r = await c.post("/api/v1/conversations/1/handoff", headers={"X-BU-ID": "BU1"})
    assert r.status_code in (200, 204)
    from ai_engine.persistence import db
    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = 1", {}
    )
    assert int(row["target_group_id"]) == 7
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_chat_auto_routing.py -v`
Expected: FAIL — 转人工端点未调路由匹配。

- [ ] **Step 3: 改 chat.py**

读 `server/src/ai_engine/api/chat.py`，定位"转人工"触发点（grep `human_pending` / `mode_change` / `to.*human` / `handoff`）。在改 `conversations.mode = 'human_pending'` 的代码点之后追加：
```python
from ai_engine.persistence import routing_rules
# 转人工时自动按规则匹配 target_group_id
await routing_rules.route_conversation_now(conv_id=conv_id, user_type=user_type)
```
（变量名按当前函数局部变量调整；`conv_id` 与 `user_type` 都应已在作用域内。）

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_chat_auto_routing.py tests/test_chat_human_mode.py -v`
Expected: 新 pass；既有 chat 测试不退化。
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/chat.py tests/test_chat_auto_routing.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/chat.py server/tests/test_chat_auto_routing.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): chat.py 转人工时自动调路由匹配落 target_group_id" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.2: chat.py 用户消息入口接入 guardrails.evaluate

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`（**前置**：非脏）
- Test: `server/tests/test_chat_guardrails.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_chat_guardrails.py
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.persistence import guardrails
    guardrails.invalidate_cache()
    await guardrails.create_rule("blocklist", "BU_BAD", "block", "EN1")
    await guardrails.create_rule("sensitive_word", "诈骗", "flag", "EN1")
    yield {}
    guardrails.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


async def test_blocklist_subject_gets_blocked(env):
    """blocklist 命中的 subject_id 发消息 → 拒绝。"""
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post("/api/v1/conversations/init", json={"resume": None},
                         headers={"X-BU-ID": "BU_BAD"})
    # 期望 init 即 block；具体 HTTP code 看 chat.py 实现（400/403 都可接受）
    assert r.status_code in (400, 403)


async def test_normal_subject_allowed(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post("/api/v1/conversations/init", json={"resume": None},
                         headers={"X-BU-ID": "BU_OK"})
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_chat_guardrails.py -v` → FAIL（chat.py 未接 guardrails）。

- [ ] **Step 3: 改 chat.py 接入 evaluate**

读 chat.py 定位"用户消息进入"入口（如 `POST /api/v1/chat` 的 body 处理处；或 `/conversations/init` 的 subject 解析处）。在拿到 `(subject_id, user_type, text)` 之后立即调用：
```python
from ai_engine.persistence import guardrails

action, reason = await guardrails.evaluate(subject_id, user_type, text or "")
if action == "block":
    raise HTTPException(403, f"guardrail blocked: {reason}")
# flag 不阻塞，但写一行 audit 留痕
if action == "flag":
    await admin_audit.log_admin_action(
        actor=subject_id, action="guardrail.flagged",
        target_type="conversation", target_id=str(conv_id or "init"),
        detail={"reason": reason},
    )
```

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_chat_guardrails.py tests/test_chat_api.py -v`
Run: `cd server && .venv/bin/ruff check src/ai_engine/api/chat.py tests/test_chat_guardrails.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/api/chat.py server/tests/test_chat_guardrails.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): chat.py 用户消息入口接入 guardrails.evaluate（block/flag）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.3: AI 自动调用接入 is_unmask_allowed("ai")

**Files:**
- Modify: `server/src/ai_engine/agent/tool_router.py` — dispatch 已接 `is_tool_allowed("ai")`；本 task 把 `unmask` 默认决策从调用方传入改为：若调用方未传，则查 `is_unmask_allowed("ai", tool)`
- Modify: `server/src/ai_engine/persistence/tool_policies.py` — `_default_unmask` 加 `role=="ai"` 默认 False 分支
- Test: `server/tests/test_tool_router_ai_unmask.py`

- [ ] **Step 1: 写失败测试**

```python
# server/tests/test_tool_router_ai_unmask.py
"""AI 自动调用的 unmask 决策：表空时默认 False；DB 显式开启即 True。"""
import pytest


async def test_ai_default_unmask_false(temp_db_url):
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    assert await tool_policies.is_unmask_allowed("query_user", "ai") is False


async def test_ai_unmask_true_when_db_says_so(temp_db_url):
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "ai",
         "allowed": 1, "unmask_allowed": 1},
    ])
    assert await tool_policies.is_unmask_allowed("query_user", "ai") is True
```

- [ ] **Step 2: 跑测试 FAIL**

Run: `cd server && .venv/bin/python -m pytest tests/test_tool_router_ai_unmask.py -v` → FAIL（`_default_unmask("ai", ...)` 当前返回 False，但只因为 `role != "engineer"`——边界 OK；第二条会 fail 是因为我们要让 DB 优先）。

> 实际上：`is_unmask_allowed` 函数已经在 M2 写好（DB 优先 + 回退默认）；`_default_unmask` 对 role!="engineer" 一律 False，所以 ai 走默认 False。第一条测试可能直接 pass；第二条因 DB 命中 unmask=1 → 走 DB 值，也应 pass。**如果两条都 pass**，无需改代码；只在 dispatch 处加从 DB 读 unmask 的逻辑（如果调用方未显式传）。

- [ ] **Step 3: 改 dispatch 默认 unmask 走 DB**

读 `server/src/ai_engine/agent/tool_router.py` 的 `dispatch`：
```python
async def dispatch(
    tool_name: str,
    params: dict[str, Any],
    user_type: str,
    subject_id: str,
    conversation_id: int,
    unmask: bool | None = None,  # 改：默认 None 表示"按 DB/默认决定"
    ...,
):
    # ... 既有 is_tool_allowed("ai") 检查保留 ...
    if unmask is None:
        from ai_engine.persistence.tool_policies import is_unmask_allowed
        unmask = await is_unmask_allowed(tool_name, "ai")
    # ...
```
所有调用方传 `unmask=True/False` 的依旧生效，本改动只影响"未传 unmask"（即 None）的情况——M2/M3b 的客服代查端点显式传 `unmask=...`，不受影响。

- [ ] **Step 4: 跑测试 + commit**

Run: `cd server && .venv/bin/python -m pytest tests/test_tool_router_ai_unmask.py tests/test_tool_router_ai_policy.py tests/test_tool_router_authz.py tests/test_runtime_redact.py -v`
Run: `cd server && .venv/bin/ruff check src/ai_engine/agent/tool_router.py tests/test_tool_router_ai_unmask.py`
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add server/src/ai_engine/agent/tool_router.py server/tests/test_tool_router_ai_unmask.py
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(admin): AI 自动调用 unmask 决策走 tool_policies(role=ai)（未显式传时）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4.4: 被动满意度弹窗（前端）

**Files:**
- Create: `web/src/components/AgentRatingPromptToast.tsx`
- Modify: `web/src/routes/ChatRoute.tsx`（前置：useChat.ts/chat.ts 非脏）

设计：监听 `chatEvents.applyUserStreamEvent` 的 `mode_change` 事件，检测 `ev.resolved === true` 时把 toast 弹出来。Toast 引用现有 `AgentRatingButton` 内的对话框组件（或直接拉起 RatingDialog）。

- [ ] **Step 1: 前置确认**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short web/src/hooks/useChat.ts web/src/hooks/chatEvents.ts web/src/api/chat.ts web/src/routes/ChatRoute.tsx`
Expected: 无输出。

- [ ] **Step 2: 实现 toast 组件**

```tsx
// web/src/components/AgentRatingPromptToast.tsx
import { useEffect, useState } from "react";

import { getRatingEligibility, submitAgentRating } from "../api/userAgentRating";

/** 监听全局 mode_change.resolved 事件，弹一个评分提示 toast。
 *  事件来源：chat.ts 流处理把 resolved 信号通过 window 事件转发：
 *    window.dispatchEvent(new CustomEvent("cs:conv-resolved", { detail: { convId } }))
 *  chat.ts 整理后由该处转发；本组件订阅事件即可。 */
export function AgentRatingPromptToast() {
  const [convId, setConvId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onResolved(e: Event) {
      const detail = (e as CustomEvent).detail as { convId: number };
      if (!detail?.convId) return;
      getRatingEligibility(detail.convId)
        .then((el) => {
          if (el.eligible && !el.already_rated) {
            setConvId(detail.convId);
            setOpen(true);
          }
        })
        .catch(() => {});
    }
    window.addEventListener("cs:conv-resolved", onResolved as EventListener);
    return () => window.removeEventListener("cs:conv-resolved", onResolved as EventListener);
  }, []);

  if (!open || convId == null) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-md bg-surface-card p-3 shadow-lg">
      <div className="mb-2 text-body2 text-ink-primary">服务已结束，请评价本次客服</div>
      <div className="flex gap-1 mb-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n}
            onClick={async () => {
              try { await submitAgentRating(convId, { rating: n }); }
              catch { /* 静默 */ }
              setOpen(false);
            }}
            className="text-status-warning text-lg">★</button>
        ))}
      </div>
      <button onClick={() => setOpen(false)}
        className="text-footnote text-ink-secondary">稍后再说</button>
    </div>
  );
}
```

- [ ] **Step 3: 改 chatEvents.ts 发 window 事件**

读 `web/src/hooks/chatEvents.ts`，找 `applyUserStreamEvent` 的 `mode_change` 分支（M3 探查时已知在 107-123 行）。在 `ev.to === "ai"` 且 `ev.resolved === true` 时，追加：
```typescript
window.dispatchEvent(new CustomEvent("cs:conv-resolved", { detail: { convId: ev.conversation_id ?? state.conversationId } }));
```
（按 chatEvents.ts 当前 state 结构调整 convId 的取法。）

- [ ] **Step 4: 挂 toast 到 ChatRoute**

读 `web/src/routes/ChatRoute.tsx`。在 `<ChatWindow />` 与 `<AgentRatingButton ... />` 之间加：
```tsx
<AgentRatingPromptToast />
```
（toast 独立监听全局事件，不需要传 props。）

- [ ] **Step 5: 验证 + commit**

Run: `cd web && pnpm typecheck && npx eslint src/components/AgentRatingPromptToast.tsx src/hooks/chatEvents.ts src/routes/ChatRoute.tsx` → 0 problems。
```bash
git -C /Users/sunchenglin/codes/tevau-cs-engine add web/src/components/AgentRatingPromptToast.tsx web/src/hooks/chatEvents.ts web/src/routes/ChatRoute.tsx
git -C /Users/sunchenglin/codes/tevau-cs-engine commit -m "feat(c-end): 客服结束后被动弹评分 toast（chatEvents 转发 + 独立组件）" -m "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

# 收尾回归

- [ ] **Step 1: 后端全套**

Run: `cd server && .venv/bin/pytest --cov=src/ai_engine --cov-report=term --cov-fail-under=75 2>&1 | tail -25`
Expected: 所有新增 pass；覆盖率 ≥75%；pre-existing 失败保持（`test_user_upload_and_view`）。

- [ ] **Step 2: 前端检查**

Run: `cd web && pnpm typecheck`
Expected: 仅 pre-existing staffFetch.ts 错保持（用户整理后可能已修；那就完全 clean）。
Run: `cd web && pnpm test:ci`
Expected: 仅 pre-existing ImageThumb test 失败保持。

- [ ] **Step 3: alembic 单 head**

Run: `cd server && .venv/bin/python -m alembic heads`
Expected: 单 head（M4 加迁移：drop_daily_token_usage / knowledge_pending_review）。

- [ ] **Step 4: git status 核对**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine status --short`
Expected: 若用户整理过脏文件，则 status 已干净；否则与原始一致。

- [ ] **Step 5: 提交链**

Run: `git -C /Users/sunchenglin/codes/tevau-cs-engine log --oneline -25`

---

## M4 完成定义（DoD）

- **Theme B**：`require_permission` 可用；StaffLayout 菜单按 RBAC 矩阵动态过滤；客服列表支持 `my_group_only`。
- **Theme C**：`daily_token_usage` 旧表已删，所有依赖切到 by-model 表；报表 metrics 支持 `count_if` + `message_feedback` 数据源；CSV 流式导出；前端 filter 加语法提示。
- **Theme D**：`is_on_shift` helper；分组下拉支持清空（前端 — = 后端 null）；心跳 60→300s + 窗口 300→360s；lookup_* 工具 input_schema 加 locale；知识库 `pending_review` 中间态；guardrails.evaluate 支持 scope_toggle。
- **Theme A**（前置完成时）：chat.py 转人工自动调路由匹配；用户消息入口接 guardrails；AI 自动调用 unmask 决策走 tool_policies；前端被动满意度弹窗。
- 后端覆盖率 ≥75%；alembic 单 head；新增 2 张表/列约束改动迁移通过 parity。

## 遗留说明（非 M4 范围，留 M5 或后续）

1. **既有 admin 路由整体迁 require_permission**：M4 仅试点 `require_permission` 依赖 + 菜单动态化。把 M1-M3 全部 admin 路由的 `Depends(require_roles(...))` 替换为 `Depends(require_permission("admin.xxx"))` 是机械工作但影响面大，分批做更安全 → M5。
2. **报表百分位/同期对比**：跨库 portable 实现复杂（PG 有 PERCENTILE_DISC，SQLite 无）。M4 用 `count_if` 已能算大多数比率类指标；真百分位 / growth 留 M5。
3. **knowledge 多人审批工作流**：M4 仅加 `pending_review` 中间态。多审批人会签 / 拒绝重提流程留 M5。
4. **chat.py 整理本身**：M4 假设用户已自行整理。若用户希望"自动整理"作为前置 task，需要单独的"chat.py 重构" plan（M5）。
5. **scope_toggle 与 user_type 联动**：M4 实现为"全局禁用 scope"；后续可扩"按 user_type 禁用"。
6. **menu API 独立端点**：M4 让 admin 直接 fetch RBAC 矩阵 + 前端过滤；将来可加 `GET /staff/api/v1/my-menu` 让任何已登录 staff 拿"我能看到的菜单项"（不暴露完整矩阵） → M5。
