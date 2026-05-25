# 客服后台统一 AppShell 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给客服工作台 + 管理后台加一个左侧固定侧边栏 AppShell，统一导航与登录守卫，让 Prompt 灰度有正式入口，各业务页去掉手工拼的导航样板。

**Architecture:** 新增 `StaffLayout`（守卫 + 侧栏 + `<Outlet/>`），用 react-router v6 嵌套路由包住「工单列表 / 工单详情 / KPI / Prompt灰度」。登录页、C 端聊天、Spectate 观战不套 shell。守卫与角色显隐集中到 Layout/侧栏；各业务页删除内部 `if(!token) nav` 守卫与 `PageHeader` 里的导航/退出/返回链接。纯展示+路由层，不动数据流/API/颜色 token。

**Tech Stack:** React 18 + Vite + TS + Tailwind + react-router-dom ^6.28；测试 vitest + @testing-library/react。所有命令工作目录 `web/`。

**测试现状（已核对）：** 现有 staff/admin 测试都**单独渲染单个页面组件**（`MemoryRouter` 包单个 `Route`）并预置 token，不渲染整个 App。因此：删除各页内部导航链接/守卫**不破坏**现有断言（`staff.test` 查 `#9`/`已接管`/`您好`、`multiStaff` 查 KPI 行、`adminPrompts` 查「需要 admin 权限」、`spectate` 查事件文案）。`adminPrompts` 的「blocks non-admin」依赖 PromptsRoute 内部 `需要 admin 权限` Alert → **必须保留该 Alert**。

**测试锚点（不得改动）：** `ui.test.tsx` 的 `bg-brand`/`status-warning` class；`adminPrompts.test.tsx` 的「需要 admin 权限」文案。

---

### Task 1: StaffLayout + 侧边栏（守卫 / 角色显隐 / 退出）

**Files:**
- Create: `web/src/components/StaffLayout.tsx`
- Test: `web/tests/staffLayout.test.tsx`

- [ ] **Step 1: 写失败测试**

创建 `web/tests/staffLayout.test.tsx`：

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffLayout } from "../src/components/StaffLayout";

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "AD1" }))}.s`;
}

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
});
afterEach(() => vi.restoreAllMocks());

function renderShell(entry = "/staff/conversations") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route element={<StaffLayout />}>
          <Route path="/staff/conversations" element={<div>列表内容</div>} />
          <Route path="/staff/kpi" element={<div>KPI内容</div>} />
          <Route path="/admin/prompts" element={<div>Prompt内容</div>} />
        </Route>
        <Route path="/staff/login" element={<div>登录页占位</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("StaffLayout", () => {
  it("无 token 时重定向到登录页", () => {
    renderShell();
    expect(screen.getByText("登录页占位")).toBeTruthy();
    expect(screen.queryByText("列表内容")).toBeNull();
  });

  it("有 token 时渲染侧栏与内容；非 admin 不显示 Prompt 灰度", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    expect(screen.getByText("列表内容")).toBeTruthy();
    expect(screen.getByText("工单")).toBeTruthy();
    expect(screen.getByText("KPI")).toBeTruthy();
    expect(screen.queryByText("Prompt 灰度")).toBeNull();
  });

  it("admin 显示 Prompt 灰度入口", () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    renderShell();
    expect(screen.getByText("Prompt 灰度")).toBeTruthy();
  });

  it("点击退出清除 token", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    fireEvent.click(screen.getByText("退出"));
    expect(localStorage.getItem("staff_jwt")).toBeNull();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm exec vitest run tests/staffLayout.test.tsx`
Expected: FAIL（`StaffLayout` 模块不存在 / 无法解析导入）。

- [ ] **Step 3: 实现 StaffLayout**

创建 `web/src/components/StaffLayout.tsx`：

```tsx
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";

import { useStaffSession } from "../hooks/useStaffSession";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

const NAV_ITEMS: { to: string; label: string; adminOnly?: boolean }[] = [
  { to: "/staff/conversations", label: "工单" },
  { to: "/staff/kpi", label: "KPI" },
  { to: "/admin/prompts", label: "Prompt 灰度", adminOnly: true },
];

function StaffSidebar() {
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r border-line bg-surface-card">
      <div className="px-4 py-4 text-sh2 text-ink-primary">◉ CS</div>
      <nav className="flex flex-1 flex-col gap-1 px-2">
        {NAV_ITEMS.filter((i) => !i.adminOnly || role === "admin").map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            className={({ isActive }) =>
              cn(
                "rounded-md px-3 py-2 text-body2 transition-colors",
                isActive
                  ? "bg-brand text-ink-onbrand"
                  : "text-ink-secondary hover:bg-surface-hover hover:text-ink-primary",
              )
            }
          >
            {i.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-col gap-2 border-t border-line px-3 py-3">
        {role && <span className="text-footnote text-ink-secondary">角色：{role}</span>}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            logout();
            nav("/staff/login");
          }}
        >
          退出
        </Button>
      </div>
    </aside>
  );
}

export function StaffLayout() {
  const { token } = useStaffSession();
  if (!token) return <Navigate to="/staff/login" replace />;
  return (
    <div className="flex h-screen">
      <StaffSidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/staffLayout.test.tsx`
Expected: PASS（4 个用例全绿）。

- [ ] **Step 5: Commit**

```bash
git add web/src/components/StaffLayout.tsx web/tests/staffLayout.test.tsx
git commit -m "feat(ui): 新增 StaffLayout 侧边栏 AppShell（守卫+角色显隐+退出）"
```

---

### Task 2: App.tsx 接入嵌套路由

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 替换 App.tsx 全文**

把 `web/src/App.tsx` 整体替换为：

```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { StaffLayout } from "./components/StaffLayout";
import { PromptsRoute } from "./routes/admin/PromptsRoute";
import { BuLoginRoute } from "./routes/BuLoginRoute";
import { ChatRoute } from "./routes/ChatRoute";
import { ConversationDetailRoute } from "./routes/staff/ConversationDetailRoute";
import { ConversationsListRoute } from "./routes/staff/ConversationsListRoute";
import { KpiRoute } from "./routes/staff/KpiRoute";
import { SpectateRoute } from "./routes/staff/SpectateRoute";
import { StaffLoginRoute } from "./routes/staff/StaffLoginRoute";
import "./styles/globals.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatRoute />} />
        <Route path="/bu/login" element={<BuLoginRoute />} />
        <Route path="/staff/login" element={<StaffLoginRoute />} />
        <Route path="/staff/conversations/:id/spectate" element={<SpectateRoute />} />
        <Route element={<StaffLayout />}>
          <Route path="/staff/conversations" element={<ConversationsListRoute />} />
          <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
          <Route path="/staff/kpi" element={<KpiRoute />} />
          <Route path="/admin/prompts" element={<PromptsRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

> 说明：`/staff/conversations/:id/spectate` 声明在 shell 组之外且路径更具体，react-router v6 按 specificity 排序，会优先于 `:id` 命中，且不套侧栏。

- [ ] **Step 2: 验证类型 + 构建**

Run: `pnpm typecheck && pnpm build`
Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat(ui): App 改为嵌套路由，staff/admin 页套入 StaffLayout"
```

---

### Task 3: ConversationsListRoute 去导航样板

**Files:**
- Modify: `web/src/routes/staff/ConversationsListRoute.tsx`

`nav` 仅用于内部守卫，`logout` 仅用于 PageHeader 退出按钮；删除后两者均无引用，需一并清理 import，否则 eslint 报未使用变量。`role`/`canSpectate`/`Link` 仍用于「旁观」链接与卡片，保留。

- [ ] **Step 1: 删除 useNavigate 导入**

把第 2 行：

```tsx
import { Link, useNavigate } from "react-router-dom";
```

改为：

```tsx
import { Link } from "react-router-dom";
```

- [ ] **Step 2: 从 useStaffSession 解构去掉 logout、去掉 nav 变量**

把：

```tsx
  const { token, role, logout } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [items, setItems] = useState<StaffConversation[]>([]);
  const [err, setErr] = useState("");
  const nav = useNavigate();
```

改为：

```tsx
  const { token, role } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [items, setItems] = useState<StaffConversation[]>([]);
  const [err, setErr] = useState("");
```

- [ ] **Step 3: 删除内部守卫，调整 useEffect 依赖**

把：

```tsx
  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    listStaffConversations(token, status)
      .then(setItems)
      .catch(() => setErr("加载失败，请重新登录"));
  }, [token, status, nav]);
```

改为：

```tsx
  useEffect(() => {
    if (!token) return;
    listStaffConversations(token, status)
      .then(setItems)
      .catch(() => setErr("加载失败，请重新登录"));
  }, [token, status]);
```

- [ ] **Step 4: PageHeader 去掉 actions（KPI 链接 + 退出按钮）**

把：

```tsx
      <PageHeader
        title="客服工作台"
        actions={
          <>
            <Button asChild variant="link" size="sm">
              <Link to="/staff/kpi">KPI</Link>
            </Button>
            <Button variant="ghost" size="sm" onClick={logout}>
              退出
            </Button>
          </>
        }
      />
```

改为：

```tsx
      <PageHeader title="客服工作台" />
```

- [ ] **Step 5: 验证（typecheck + 该页相关测试）**

Run: `pnpm typecheck && pnpm exec vitest run tests/staff.test.tsx`
Expected: PASS（`renders conversations` 仍查到 `#9`；无未使用变量类型错误）。

- [ ] **Step 6: Commit**

```bash
git add web/src/routes/staff/ConversationsListRoute.tsx
git commit -m "feat(ui): 工单列表去掉自带导航/退出，守卫交给 StaffLayout"
```

---

### Task 4: KpiRoute 去导航样板

**Files:**
- Modify: `web/src/routes/staff/KpiRoute.tsx`

`Link` 仅用于「返回工作台」、`nav` 仅用于守卫；删除后均无引用，连带清理 import。

- [ ] **Step 1: 删除 Link / useNavigate 导入**

把第 2 行：

```tsx
import { Link, useNavigate } from "react-router-dom";
```

整行删除（KpiRoute 不再用 react-router-dom 的任何具名导出）。

- [ ] **Step 2: 删除 nav 变量与内部守卫**

把：

```tsx
export function KpiRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [rows, setRows] = useState<StaffKpi[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    getKpi(token)
      .then(setRows)
      .catch(() => setErr("加载失败"));
  }, [token, nav]);
```

改为：

```tsx
export function KpiRoute() {
  const { token } = useStaffSession();
  const [rows, setRows] = useState<StaffKpi[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    getKpi(token)
      .then(setRows)
      .catch(() => setErr("加载失败"));
  }, [token]);
```

- [ ] **Step 3: PageHeader 去掉「返回工作台」actions**

把：

```tsx
      <PageHeader
        title="客服 KPI 看板"
        actions={
          <Button asChild variant="link" size="sm">
            <Link to="/staff/conversations">返回工作台</Link>
          </Button>
        }
      />
```

改为：

```tsx
      <PageHeader title="客服 KPI 看板" />
```

- [ ] **Step 4: 清理 Button 导入（已无引用）**

确认文件内 `Button` 是否还有其他用法（KpiRoute 仅在上面被删的 actions 用过 Button）。删除第 6 行：

```tsx
import { Button } from "../../components/ui/button";
```

- [ ] **Step 5: 验证**

Run: `pnpm typecheck && pnpm exec vitest run tests/multiStaff.test.tsx`
Expected: PASS（`renders kpi rows` 仍查到 `AG1`/`75%`/`2分5秒`）。

- [ ] **Step 6: Commit**

```bash
git add web/src/routes/staff/KpiRoute.tsx
git commit -m "feat(ui): KPI 页去掉返回链接，导航走 StaffLayout"
```

---

### Task 5: PromptsRoute 去返回按钮（保留 admin 兜底 Alert）

**Files:**
- Modify: `web/src/routes/admin/PromptsRoute.tsx`

入口已仅 admin 可见，删除页内「返回」按钮与 `nav`。**保留** `需要 admin 权限` 的 `setErr`/`Alert`（双保险 + `adminPrompts` 测试依赖）。

- [ ] **Step 1: 删除 useNavigate 导入与 nav 变量**

把第 2 行：

```tsx
import { useNavigate } from "react-router-dom";
```

整行删除。把：

```tsx
  const { token, role } = useStaffSession();
  const nav = useNavigate();
```

改为：

```tsx
  const { token, role } = useStaffSession();
```

- [ ] **Step 2: PageHeader 去掉「返回」按钮**

把：

```tsx
      <PageHeader
        title="Prompt 灰度管理"
        actions={
          <Button variant="ghost" size="sm" onClick={() => nav("/staff/conversations")}>
            返回
          </Button>
        }
      />
```

改为：

```tsx
      <PageHeader title="Prompt 灰度管理" />
```

> `Button` 仍用于底部「保存」，保留其 import。`需要 admin 权限` 的 `setErr` 与 `<Alert variant="error">` 保持不动。

- [ ] **Step 3: 验证**

Run: `pnpm typecheck && pnpm exec vitest run tests/adminPrompts.test.tsx`
Expected: PASS（`blocks non-admin` 仍查到「需要 admin 权限」；`loads versions and saves rollout` 仍能保存）。

- [ ] **Step 4: Commit**

```bash
git add web/src/routes/admin/PromptsRoute.tsx
git commit -m "feat(ui): Prompt 灰度页去掉返回按钮（入口移入侧栏）"
```

---

### Task 6: ConversationDetailRoute 去内部守卫

**Files:**
- Modify: `web/src/routes/staff/ConversationDetailRoute.tsx`

`nav` 仅用于守卫（行 75），删除后无引用；`useParams` 仍需要。PageHeader 的 actions 是页面级操作（草稿模式/接管/释放），**保留不动**。

- [ ] **Step 1: 改导入，去掉 useNavigate**

把第 2 行：

```tsx
import { useNavigate, useParams } from "react-router-dom";
```

改为：

```tsx
import { useParams } from "react-router-dom";
```

- [ ] **Step 2: 删除 nav 变量**

把：

```tsx
  const { token, role } = useStaffSession();
  const canUseTools = role === "senior" || role === "engineer";
  const nav = useNavigate();
```

改为：

```tsx
  const { token, role } = useStaffSession();
  const canUseTools = role === "senior" || role === "engineer";
```

- [ ] **Step 3: 删除守卫 useEffect**

把：

```tsx
  useEffect(() => {
    if (!token) nav("/staff/login");
  }, [token, nav]);

```

整段删除（连同其后空行）。

> 注意：确认 `useEffect` 在文件内仍被其他逻辑使用（`useStaffStream` 内部用了 `useEffect`，但那是另一处；本组件主体若仅此一处用 `useEffect`，删除后需检查 `useEffect` 是否还在第 1 行 import 中被引用——`ConversationDetailRoute` 主体除此守卫外不再直接用 `useEffect`，但 `useStaffStream` 与 import 同文件共用第 1 行的 `useEffect` 导入，故 **import 保留不动**）。

- [ ] **Step 4: 验证**

Run: `pnpm typecheck && pnpm exec vitest run tests/staff.test.tsx`
Expected: PASS（`ConversationDetailRoute` 的 `take then send` 仍查到「已接管」「您好」）。

- [ ] **Step 5: Commit**

```bash
git add web/src/routes/staff/ConversationDetailRoute.tsx
git commit -m "feat(ui): 工单详情去掉内部登录守卫（交给 StaffLayout）"
```

---

### Task 7: SpectateRoute 补「返回工作台」入口（保持全屏，不套 shell）

**Files:**
- Modify: `web/src/routes/staff/SpectateRoute.tsx`

Spectate 不套侧栏（全屏沉浸），保留自身守卫，但需要一个返回工作台的入口（当前没有）。

- [ ] **Step 1: 改导入，加入 Link**

把第 2 行：

```tsx
import { useNavigate, useParams } from "react-router-dom";
```

改为：

```tsx
import { Link, useNavigate, useParams } from "react-router-dom";
```

- [ ] **Step 2: 标题行加「返回工作台」链接**

把：

```tsx
      <h2 className="mb-1 text-sh2 text-ink-primary">旁观会话 #{convId}</h2>
```

改为：

```tsx
      <div className="mb-1 flex items-center gap-2">
        <h2 className="flex-1 text-sh2 text-ink-primary">旁观会话 #{convId}</h2>
        <Link to="/staff/conversations" className="text-body3 text-brand hover:underline">
          返回工作台
        </Link>
      </div>
```

> `nav` 与守卫保留不动（Spectate 不在 Layout 下，需自带守卫）。

- [ ] **Step 3: 验证**

Run: `pnpm typecheck && pnpm exec vitest run tests/spectate.test.tsx`
Expected: PASS（`renders streamed events read-only` 仍查到「AI：…」「用户：…」）。

- [ ] **Step 4: Commit**

```bash
git add web/src/routes/staff/SpectateRoute.tsx
git commit -m "feat(ui): 观战页补返回工作台入口（保持全屏）"
```

---

### Task 8: C 端核对 + 全量验证 + 格式化收尾

**Files:** 视核对结果可能无改动。

- [ ] **Step 1: 核对 C 端聊天页不受影响**

Run: `grep -n "StaffLayout\|useStaffSession\|/staff/" web/src/routes/ChatRoute.tsx web/src/components/ChatWindow.tsx`
Expected: 无输出（C 端聊天不依赖 staff 会话/布局；`/` 路由在 App 中保持独立，未套 shell）。结论记录：C 端无需改动。

- [ ] **Step 2: 全量验证**

Run: `pnpm typecheck && pnpm test:ci && pnpm build`
Expected: 全 PASS（含新增 `staffLayout.test.tsx`）。

- [ ] **Step 3: 仅对改动文件格式化与 lint**

Run（在 `web/`）：

```bash
pnpm exec prettier --write src/App.tsx src/components/StaffLayout.tsx tests/staffLayout.test.tsx src/routes/staff/ConversationsListRoute.tsx src/routes/staff/KpiRoute.tsx src/routes/admin/PromptsRoute.tsx src/routes/staff/ConversationDetailRoute.tsx src/routes/staff/SpectateRoute.tsx
pnpm exec eslint src/components/StaffLayout.tsx src/routes/staff/ConversationsListRoute.tsx src/routes/staff/KpiRoute.tsx src/routes/admin/PromptsRoute.tsx src/routes/staff/ConversationDetailRoute.tsx src/routes/staff/SpectateRoute.tsx src/App.tsx --max-warnings=0
```

Expected: prettier 无残留、eslint 0 warning。

- [ ] **Step 4: 人工核对（pnpm dev）**

登录 staff → 进入工作台，确认：左侧固定侧栏（工单/KPI；admin 额外 Prompt 灰度）、激活项 cyan 高亮、退出可用、各页内容区正常滚动；非 admin 看不到 Prompt 灰度；直接访问 `/admin/prompts` 未登录跳登录页；观战页全屏且有「返回工作台」；C 端聊天 `/` 不受影响。

- [ ] **Step 5: Commit（若 prettier 有改动）**

```bash
git add web/
git commit -m "chore(ui): AppShell 收尾格式化"
```

---

## Self-Review 记录

- **Spec 覆盖：**
  - §4.1 路由结构 → Task 2。
  - §4.2 StaffLayout 守卫/布局 → Task 1 + Task 8 验证。
  - §4.3 StaffSidebar 导航/admin 显隐/退出 → Task 1。
  - §5 各页改造（List/Detail/Kpi/Prompts/Spectate）→ Task 3/6/4/5/7。
  - §6 视觉规范 → Task 1 侧栏 class（cyan 激活、surface-card、line 边框）。
  - §7 测试影响 → 各 Task 验证步 + Task 1 新增 Layout 测试；保留 PromptsRoute admin Alert。
  - §3 决策（Spectate 不套/全屏、C 端仅核对）→ Task 7 / Task 8 Step1。
  - §8 工程约束 → Task 8 Step2-3。无遗漏。
- **占位符扫描：** 无 TBD/TODO；每个改动步骤含 exact 前后代码。
- **类型一致：** `StaffLayout`/`StaffSidebar`/`NAV_ITEMS` 命名在 Task 1 定义并在 Task 2 引用一致；各页删除的 `nav`/`logout`/`Link`/`Button`/`useNavigate` 引用已逐一核对删除，避免未使用变量。
- **风险点：** Task 6 删除守卫 `useEffect` 后，import 第 1 行的 `useEffect` 仍被 `useStaffStream` 使用，import 保留——已在步骤内标注。
