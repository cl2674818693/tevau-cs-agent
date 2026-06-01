# 管理后台 shadcn-admin 全量重写 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/` 下 30 条 admin + staff Route 的 UI 全量重写为 shadcn-admin 风格（5 分组 Sidebar / Topbar / CommandPalette / 亮暗双主题），ChatRoute 不动。

**Architecture:** Token 双轨——admin/staff/BuLogin/Spectate 走 shadcn CSS 变量；ChatRoute 守自有 `brand/ink/surface/line` token。新 `AppShell` 替换 `StaffLayout`。分 Phase 0-5 增量 cutover，每 Phase 独立 PR 可上线。

**Tech Stack:** React 18 / Vite 5 / TS 5.5（不升）+ Tailwind 3.4 + tailwindcss-animate + @radix-ui/* + @tanstack/react-table + react-hook-form + zod + sonner + cmdk + recharts。

**Spec:** `docs/superpowers/specs/2026-06-01-admin-shadcn-redesign-design.md`

---

## 文件结构

新增：

```
web/components.json                                 # shadcn CLI 配置
web/src/components/app-shell/
├── AppShell.tsx                                    # 总外壳，替换 StaffLayout
├── AppSidebar.tsx                                  # 桌面侧栏（CollapsibleGroup x5）
├── AppTopbar.tsx                                   # Topbar
├── CommandPalette.tsx                              # ⌘K 命令面板
├── ThemeToggle.tsx                                 # 亮/暗/system 切换
├── UserMenu.tsx                                    # 头像 DropdownMenu
├── Breadcrumbs.tsx                                 # Topbar 面包屑
├── MobileSidebar.tsx                               # < md 用 Sheet 包 AppSidebar
├── nav-config.ts                                   # 5 分组导航定义
└── perm-map.ts                                     # PATH_TO_PERM 集中
web/src/components/ui/                              # shadcn 新组件（pnpm dlx shadcn add）
├── sidebar.tsx sheet.tsx separator.tsx
├── scroll-area.tsx breadcrumb.tsx collapsible.tsx
├── form.tsx select.tsx checkbox.tsx radio-group.tsx
├── switch.tsx textarea.tsx label.tsx popover.tsx
├── calendar.tsx date-picker.tsx sonner.tsx skeleton.tsx
├── dialog.tsx dropdown-menu.tsx tabs.tsx command.tsx
└── (重写 button/card/input/table/badge/alert)
web/src/providers/ThemeProvider.tsx                 # ThemeContext
web/src/hooks/useTheme.ts                           # useTheme()
web/src/hooks/useSidebarCollapsed.ts                # 折叠状态 localStorage
web/src/routes/ForbiddenRoute.tsx                   # 403 占位页
web/src/components/admin/KpiCard.tsx                # Phase 2 通用 KPI 卡
web/src/components/admin/data-table/                # 通用 DataTable
├── DataTable.tsx
├── DataTableToolbar.tsx
├── DataTableColumnHeader.tsx
└── DataTablePagination.tsx
```

修改：

```
web/package.json                                    # 加 deps
web/tailwind.config.ts                              # darkMode + shadcn theme.extend.colors
web/src/styles/globals.css                          # :root + .dark CSS vars
web/src/App.tsx                                     # StaffLayout → AppShell + ForbiddenRoute
web/src/components/StaffLayout.tsx                  # Phase 5 删除
web/src/routes/{admin,staff}/*.tsx                  # Phase 1-4 逐页重写
```

---

# Phase 0: AppShell 基建

**目标：** 装依赖、接入 shadcn token 双轨、用 `AppShell` 替换 `StaffLayout`、加 Topbar / CommandPalette / 主题切换 / 403 页。所有现有页面套进新 Shell，**页面内部 UI 不动**。PR 可单独合并部署。

**分支：** `feat/admin-shadcn-phase-0`

---

### Task 0.1: 准备分支与依赖锁定

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 创建 Phase 0 分支**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine
git checkout feat/admin-shadcn-redesign  # 已存在，含 spec
git checkout -b feat/admin-shadcn-phase-0
```

- [ ] **Step 2: 安装运行时依赖**

```bash
cd web
pnpm add @tanstack/react-table react-hook-form @hookform/resolvers zod sonner cmdk recharts date-fns react-day-picker
pnpm add @radix-ui/react-checkbox @radix-ui/react-collapsible @radix-ui/react-dropdown-menu @radix-ui/react-label @radix-ui/react-popover @radix-ui/react-radio-group @radix-ui/react-scroll-area @radix-ui/react-select @radix-ui/react-separator @radix-ui/react-switch @radix-ui/react-tabs
```

- [ ] **Step 3: 验证安装**

```bash
cd web && pnpm install
```

Expected: 无 ERESOLVE / peer warning。

- [ ] **Step 4: 提交**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine
git add web/package.json web/pnpm-lock.yaml
git commit -m "chore(web): add shadcn-admin runtime deps (Phase 0)"
```

---

### Task 0.2: 初始化 shadcn CLI 配置

**Files:**
- Create: `web/components.json`

- [ ] **Step 1: 写 `components.json`**

写到 `web/components.json`：

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/styles/globals.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "iconLibrary": "lucide"
}
```

- [ ] **Step 2: 配置 `@/*` 路径别名**

修改 `web/tsconfig.json`，在 `compilerOptions` 加（若已有 `paths` 合并）：

```jsonc
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

修改 `web/vite.config.ts`，在 `defineConfig` 返回对象加 `resolve`：

```ts
import path from "path";
// ...
return {
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: { /* 现有 */ },
  test: { /* 现有 */ },
};
```

- [ ] **Step 3: 验证 typecheck 仍过**

```bash
cd web && pnpm typecheck
```

Expected: 0 errors。

- [ ] **Step 4: 提交**

```bash
git add web/components.json web/tsconfig.json web/vite.config.ts
git commit -m "chore(web): init shadcn cli config + @/* alias"
```

---

### Task 0.3: Tailwind & globals 接入 shadcn token

**Files:**
- Modify: `web/tailwind.config.ts`
- Modify: `web/src/styles/globals.css`

- [ ] **Step 1: 修改 tailwind.config.ts**

在现有 `theme.extend` **顶部追加** shadcn 颜色与圆角；现有 `colors` / `fontSize` / `fontFamily` 等**全部保留**：

```ts
// tailwind.config.ts (示意，合并到现有)
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // shadcn 体系（新增）
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        // 自有 token（保留给 ChatRoute）
        brand: { /* 现有 */ },
        ink: { /* 现有 */ },
        surface: { /* 现有 */ },
        line: "#E2E8F0",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      // fontSize / fontFamily / animation 等现有内容保持
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

**注意：** `colors.brand/ink/surface/line` 与现有保持一致，不要删除。

- [ ] **Step 2: 修改 globals.css，加 shadcn 变量**

在 `web/src/styles/globals.css` 现有 `@tailwind utilities;` 后追加：

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --card: 0 0% 100%;
    --card-foreground: 240 10% 3.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 240 10% 3.9%;
    --primary: 238 71% 56%;             /* indigo-600 #4f46e5 */
    --primary-foreground: 0 0% 100%;
    --secondary: 240 4.8% 95.9%;
    --secondary-foreground: 240 5.9% 10%;
    --muted: 240 4.8% 95.9%;
    --muted-foreground: 240 3.8% 46.1%;
    --accent: 240 4.8% 95.9%;
    --accent-foreground: 240 5.9% 10%;
    --destructive: 0 84% 60%;
    --destructive-foreground: 0 0% 100%;
    --border: 240 5.9% 90%;
    --input: 240 5.9% 90%;
    --ring: 238 71% 56%;
    --radius: 0.5rem;

    --sidebar-background: 0 0% 98%;
    --sidebar-foreground: 240 5.3% 26.1%;
    --sidebar-primary: 238 71% 56%;
    --sidebar-primary-foreground: 0 0% 100%;
    --sidebar-accent: 240 4.8% 95.9%;
    --sidebar-accent-foreground: 240 5.9% 10%;
    --sidebar-border: 240 5.9% 90%;
    --sidebar-ring: 238 71% 56%;
  }

  .dark {
    --background: 240 10% 3.9%;
    --foreground: 0 0% 98%;
    --card: 240 10% 3.9%;
    --card-foreground: 0 0% 98%;
    --popover: 240 10% 3.9%;
    --popover-foreground: 0 0% 98%;
    --primary: 238 71% 66%;
    --primary-foreground: 240 5.9% 10%;
    --secondary: 240 3.7% 15.9%;
    --secondary-foreground: 0 0% 98%;
    --muted: 240 3.7% 15.9%;
    --muted-foreground: 240 5% 64.9%;
    --accent: 240 3.7% 15.9%;
    --accent-foreground: 0 0% 98%;
    --destructive: 0 62.8% 50%;
    --destructive-foreground: 0 0% 98%;
    --border: 240 3.7% 15.9%;
    --input: 240 3.7% 15.9%;
    --ring: 238 71% 66%;

    --sidebar-background: 240 5.9% 10%;
    --sidebar-foreground: 240 4.8% 95.9%;
    --sidebar-primary: 238 71% 66%;
    --sidebar-primary-foreground: 240 5.9% 10%;
    --sidebar-accent: 240 3.7% 15.9%;
    --sidebar-accent-foreground: 240 4.8% 95.9%;
    --sidebar-border: 240 3.7% 15.9%;
    --sidebar-ring: 238 71% 66%;
  }
}

@layer base {
  * { @apply border-border; }
}
```

**不要动 body 现有 `background: #f7f8fa; color: #0f172a;`**（仅 ChatRoute 用，AppShell 自己控背景）。

- [ ] **Step 3: 跑 build 确认 css 编译过**

```bash
cd web && pnpm build
```

Expected: 0 errors，dist 生成。

- [ ] **Step 4: 提交**

```bash
git add web/tailwind.config.ts web/src/styles/globals.css
git commit -m "feat(web): add shadcn css vars + dark mode token namespace"
```

---

### Task 0.4: ThemeProvider + useTheme hook

**Files:**
- Create: `web/src/providers/ThemeProvider.tsx`
- Create: `web/src/hooks/useTheme.ts`
- Create: `web/tests/theme.test.tsx`

- [ ] **Step 1: 写测试**

写到 `web/tests/theme.test.tsx`：

```tsx
import { act, render, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { ThemeProvider } from "@/providers/ThemeProvider";
import { useTheme } from "@/hooks/useTheme";

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("默认 system 模式", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    expect(result.current.theme).toBe("system");
  });

  it("setTheme('dark') 写 localStorage 并加 html.dark", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    act(() => result.current.setTheme("dark"));
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("setTheme('light') 移除 html.dark", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    act(() => result.current.setTheme("dark"));
    act(() => result.current.setTheme("light"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd web && pnpm vitest run tests/theme.test.tsx
```

Expected: FAIL，模块未实现。

- [ ] **Step 3: 实现 ThemeProvider**

写到 `web/src/providers/ThemeProvider.tsx`：

```tsx
import { createContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark" | "system";

type Ctx = {
  theme: Theme;
  setTheme: (t: Theme) => void;
};

export const ThemeContext = createContext<Ctx | null>(null);

function resolveSystemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyDark(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

/** AppShell 外层包裹。ChatRoute 不包，进入时副作用清掉 dark 类。 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme");
    return saved === "light" || saved === "dark" ? saved : "system";
  });

  useEffect(() => {
    if (theme === "system") {
      applyDark(resolveSystemDark());
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const listener = () => applyDark(resolveSystemDark());
      mq.addEventListener("change", listener);
      return () => mq.removeEventListener("change", listener);
    }
    applyDark(theme === "dark");
  }, [theme]);

  const value = useMemo<Ctx>(
    () => ({
      theme,
      setTheme: (t) => {
        if (t === "system") localStorage.removeItem("theme");
        else localStorage.setItem("theme", t);
        setThemeState(t);
      },
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
```

写到 `web/src/hooks/useTheme.ts`：

```ts
import { useContext } from "react";
import { ThemeContext } from "@/providers/ThemeProvider";

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be inside <ThemeProvider>");
  return ctx;
}
```

- [ ] **Step 4: 跑测试通过**

```bash
cd web && pnpm vitest run tests/theme.test.tsx
```

Expected: 3 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/providers/ThemeProvider.tsx web/src/hooks/useTheme.ts web/tests/theme.test.tsx
git commit -m "feat(web): ThemeProvider + useTheme hook"
```

---

### Task 0.5: 用 shadcn CLI 一次拉齐基础组件

**Files:**
- Create: `web/src/components/ui/{button,card,input,table,badge,alert,sheet,separator,scroll-area,breadcrumb,collapsible,form,select,checkbox,radio-group,switch,textarea,label,popover,calendar,sonner,skeleton,dialog,dropdown-menu,tabs,command,tooltip}.tsx`

- [ ] **Step 1: 备份现有组件**

旧版本保留在 git 历史里足够。直接覆盖。

- [ ] **Step 2: 批量拉 shadcn 组件**

```bash
cd web
pnpm dlx shadcn@latest add button card input table badge alert sheet separator scroll-area breadcrumb collapsible form select checkbox radio-group switch textarea label popover calendar sonner skeleton dialog dropdown-menu tabs command tooltip --overwrite --yes
```

Expected: 26 个文件写入 `src/components/ui/`，所有依赖（如 `@radix-ui/react-tooltip` 已装则跳过）确认安装。

- [ ] **Step 3: 写 date-picker（shadcn 未提供，手写组合 popover+calendar）**

写到 `web/src/components/ui/date-picker.tsx`：

```tsx
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export function DatePicker({
  date,
  onChange,
  placeholder = "选择日期",
}: {
  date?: Date;
  onChange: (d: Date | undefined) => void;
  placeholder?: string;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn("w-[200px] justify-start text-left font-normal", !date && "text-muted-foreground")}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {date ? format(date, "yyyy-MM-dd") : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar mode="single" selected={date} onSelect={onChange} initialFocus />
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: typecheck + lint**

```bash
cd web && pnpm typecheck && pnpm lint
```

Expected: 0 errors / 0 warnings。如果旧测试（`tests/ui.test.tsx` / `tests/components.test.tsx`）依赖旧 button/card/input/badge/alert API，**这一步会暴露 import 或断言错**，Task 0.6 一并修。

- [ ] **Step 5: 提交**

```bash
git add web/src/components/ui/
git commit -m "feat(web): add shadcn ui primitives (sheet/sidebar/form/...)"
```

---

### Task 0.6: 修复旧测试对新 ui 组件的断言

**Files:**
- Modify: `web/tests/ui.test.tsx`、`web/tests/components.test.tsx`（按 Task 0.5 typecheck/test 报错定位）

- [ ] **Step 1: 跑测试看挂哪几个**

```bash
cd web && pnpm vitest run
```

把 FAIL 列表记下来。失败原因通常是：旧 button 用 `text-body1 bg-brand`，shadcn 版用 `text-sm bg-primary`。

- [ ] **Step 2: 改 className 断言**

每个失败用例：替换断言中的 token 类名。例如：

```tsx
// 旧
expect(btn.className).toContain("bg-brand");
// 新
expect(btn.className).toContain("bg-primary");
```

如果旧测试断言的是行为而非样式，保持不变。

- [ ] **Step 3: 跑测试全绿**

```bash
cd web && pnpm vitest run
```

Expected: 全 PASS。

- [ ] **Step 4: 提交**

```bash
git add web/tests/
git commit -m "test(web): update ui assertions for shadcn primitives"
```

---

### Task 0.7: 导航配置与权限映射搬出

**Files:**
- Create: `web/src/components/app-shell/nav-config.ts`
- Create: `web/src/components/app-shell/perm-map.ts`

- [ ] **Step 1: 写 perm-map.ts**

写到 `web/src/components/app-shell/perm-map.ts`：

```ts
/** path → RBAC permission_key 映射；从原 StaffLayout.tsx:80-99 搬出。 */
export const PATH_TO_PERM: Record<string, string> = {
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

- [ ] **Step 2: 写 nav-config.ts**

写到 `web/src/components/app-shell/nav-config.ts`：

```ts
import {
  Activity, BarChart3, BookOpen, CalendarClock, ClipboardCheck,
  FileEdit, FileSpreadsheet, Headphones, Inbox, KeySquare,
  LayoutDashboard, Lightbulb, type LucideIcon, Route, ScrollText,
  Shield, ShieldAlert, ShieldCheck, SlidersHorizontal, Ticket,
  Timer, UserCog, Users, Users2, Wallet,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  short?: string;
  icon: LucideIcon;
  roles?: string[];
};

export type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workbench",
    label: "工作台",
    items: [
      { to: "/staff/conversations", label: "会话", short: "会话", icon: Inbox },
      { to: "/staff/tickets", label: "工单", icon: Ticket },
      { to: "/staff/kpi", label: "KPI", icon: BarChart3 },
      { to: "/staff/insights", label: "知识缺口", short: "缺口", icon: Lightbulb },
      { to: "/staff/audits", label: "工具审计", short: "审计", icon: ShieldCheck },
    ],
  },
  {
    id: "ops",
    label: "运营看板",
    items: [
      { to: "/admin/dashboard", label: "数据大盘", icon: LayoutDashboard, roles: ["supervisor", "manager", "admin"] },
      { to: "/admin/sla", label: "SLA", icon: Timer, roles: ["supervisor", "admin"] },
      { to: "/admin/performance", label: "客服绩效", icon: UserCog, roles: ["supervisor", "admin"] },
      { to: "/admin/cost", label: "成本大盘", icon: Wallet, roles: ["engineer", "manager", "admin"] },
      { to: "/admin/reports", label: "自定义报表", icon: FileSpreadsheet, roles: ["supervisor", "manager", "admin"] },
    ],
  },
  {
    id: "qa",
    label: "质检与审计",
    items: [
      { to: "/admin/qa", label: "会话质检", icon: ClipboardCheck, roles: ["supervisor", "admin"] },
      { to: "/admin/audit", label: "操作审计", icon: ScrollText, roles: ["engineer", "admin"] },
    ],
  },
  {
    id: "ai",
    label: "AI 配置",
    items: [
      { to: "/admin/prompt-editor", label: "Prompt 编辑", icon: FileEdit, roles: ["engineer", "admin"] },
      { to: "/admin/prompts", label: "Prompt 灰度", icon: SlidersHorizontal, roles: ["admin"] },
      { to: "/admin/knowledge", label: "知识库", icon: BookOpen, roles: ["supervisor", "engineer", "admin"] },
      { to: "/admin/tools", label: "工具策略", icon: KeySquare, roles: ["engineer", "admin"] },
      { to: "/admin/guardrails", label: "范围拦截", icon: ShieldAlert, roles: ["engineer", "admin"] },
    ],
  },
  {
    id: "people",
    label: "坐席与权限",
    items: [
      { to: "/admin/staff", label: "客服账号", icon: Users, roles: ["admin"] },
      { to: "/admin/staff-groups", label: "客服分组", icon: Users2, roles: ["supervisor", "admin"] },
      { to: "/admin/presence", label: "在线状态", icon: Activity, roles: ["supervisor", "admin"] },
      { to: "/admin/shifts", label: "排班", icon: CalendarClock, roles: ["supervisor", "admin"] },
      { to: "/admin/routing", label: "会话路由", icon: Route, roles: ["supervisor", "admin"] },
      { to: "/admin/rbac", label: "角色权限", icon: Shield, roles: ["admin"] },
    ],
  },
];

export const APP_BRAND_ICON = Headphones;
export const APP_BRAND_NAME = "Tevau 客服 AI 引擎";
```

- [ ] **Step 3: typecheck**

```bash
cd web && pnpm typecheck
```

Expected: 0 errors。

- [ ] **Step 4: 提交**

```bash
git add web/src/components/app-shell/
git commit -m "feat(web): nav-config 5 分组 + perm-map"
```

---

### Task 0.8: useSidebarCollapsed hook

**Files:**
- Create: `web/src/hooks/useSidebarCollapsed.ts`
- Create: `web/tests/sidebarCollapsed.test.tsx`

- [ ] **Step 1: 写测试**

写到 `web/tests/sidebarCollapsed.test.tsx`：

```tsx
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";

describe("useSidebarCollapsed", () => {
  beforeEach(() => localStorage.clear());

  it("默认全展开（无 localStorage）", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("toggle 写 localStorage", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(true);
    expect(localStorage.getItem("sidebar-collapsed")).toContain("workbench");
  });

  it("再次 toggle 还原", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("workbench"));
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(false);
  });
});
```

- [ ] **Step 2: 跑测试 FAIL**

```bash
cd web && pnpm vitest run tests/sidebarCollapsed.test.tsx
```

Expected: FAIL，模块未实现。

- [ ] **Step 3: 写 hook**

写到 `web/src/hooks/useSidebarCollapsed.ts`：

```ts
import { useCallback, useState } from "react";

const KEY = "sidebar-collapsed";

function readSet(): Set<string> {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

export function useSidebarCollapsed() {
  const [set, setSet] = useState<Set<string>>(readSet);

  const toggle = useCallback((groupId: string) => {
    setSet((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      localStorage.setItem(KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  const collapsed = useCallback((groupId: string) => set.has(groupId), [set]);

  return { collapsed, toggle };
}
```

- [ ] **Step 4: 跑测试通过**

```bash
cd web && pnpm vitest run tests/sidebarCollapsed.test.tsx
```

Expected: 3 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/hooks/useSidebarCollapsed.ts web/tests/sidebarCollapsed.test.tsx
git commit -m "feat(web): useSidebarCollapsed hook (localStorage)"
```

---

### Task 0.9: AppSidebar 桌面侧栏

**Files:**
- Create: `web/src/components/app-shell/AppSidebar.tsx`
- Create: `web/tests/appSidebar.test.tsx`

- [ ] **Step 1: 写测试**

写到 `web/tests/appSidebar.test.tsx`：

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppSidebar } from "@/components/app-shell/AppSidebar";

vi.mock("@/hooks/useStaffSession", () => ({
  useStaffSession: () => ({ role: "admin", token: "tk", logout: vi.fn() }),
}));
vi.mock("@/hooks/useDynamicMenu", () => ({ useDynamicMenu: () => ({ matrix: null }) }));

describe("AppSidebar", () => {
  beforeEach(() => localStorage.clear());

  it("admin 角色能看到 5 个分组", () => {
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("工作台")).toBeInTheDocument();
    expect(screen.getByText("运营看板")).toBeInTheDocument();
    expect(screen.getByText("质检与审计")).toBeInTheDocument();
    expect(screen.getByText("AI 配置")).toBeInTheDocument();
    expect(screen.getByText("坐席与权限")).toBeInTheDocument();
  });

  it("点击分组标题折叠/展开", () => {
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("数据大盘")).toBeInTheDocument();
    fireEvent.click(screen.getByText("运营看板"));
    expect(screen.queryByText("数据大盘")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试 FAIL**

```bash
cd web && pnpm vitest run tests/appSidebar.test.tsx
```

Expected: FAIL，组件未实现。

- [ ] **Step 3: 写组件**

写到 `web/src/components/app-shell/AppSidebar.tsx`：

```tsx
import { ChevronDown } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";
import { useStaffSession } from "@/hooks/useStaffSession";
import { cn } from "@/lib/utils";
import { APP_BRAND_ICON, APP_BRAND_NAME, NAV_GROUPS, type NavItem } from "./nav-config";
import { PATH_TO_PERM } from "./perm-map";

function canAccess(item: NavItem, role: string | null, matrix: ReturnType<typeof useDynamicMenu>["matrix"]): boolean {
  const permKey = PATH_TO_PERM[item.to];
  if (matrix && permKey && role) return matrix.matrix[role]?.[permKey] === true;
  return !item.roles || (role != null && item.roles.includes(role));
}

export function AppSidebar() {
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();
  const { collapsed, toggle } = useSidebarCollapsed();
  const Brand = APP_BRAND_ICON;

  return (
    <aside className="hidden h-full w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <Brand className="h-5 w-5 text-primary" aria-hidden />
        <span className="text-sm font-semibold">{APP_BRAND_NAME}</span>
      </div>
      <ScrollArea className="flex-1 px-2 py-2">
        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((i) => canAccess(i, role, matrix));
          if (visible.length === 0) return null;
          const isOpen = !collapsed(group.id);
          return (
            <Collapsible key={group.id} open={isOpen} onOpenChange={() => toggle(group.id)} className="mb-1">
              <CollapsibleTrigger className="flex w-full items-center justify-between rounded px-3 py-1.5 text-xs font-semibold text-sidebar-foreground/60 hover:bg-sidebar-accent">
                <span>{group.label}</span>
                <ChevronDown className={cn("h-3 w-3 transition-transform", !isOpen && "-rotate-90")} aria-hidden />
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-0.5 space-y-0.5">
                {visible.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-sidebar-primary text-sidebar-primary-foreground"
                          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                    {item.label}
                  </NavLink>
                ))}
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </ScrollArea>
    </aside>
  );
}
```

- [ ] **Step 4: 跑测试通过**

```bash
cd web && pnpm vitest run tests/appSidebar.test.tsx
```

Expected: 2 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/components/app-shell/AppSidebar.tsx web/tests/appSidebar.test.tsx
git commit -m "feat(web): AppSidebar 5 分组可折叠 + RBAC 过滤"
```

---

### Task 0.10: ThemeToggle 控件

**Files:**
- Create: `web/src/components/app-shell/ThemeToggle.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/ThemeToggle.tsx`：

```tsx
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/hooks/useTheme";

export function ThemeToggle() {
  const { setTheme, theme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="切换主题">
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme("light")}>
          <Sun className="mr-2 h-4 w-4" /> 亮色{theme === "light" && " ✓"}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          <Moon className="mr-2 h-4 w-4" /> 暗色{theme === "dark" && " ✓"}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>
          <Monitor className="mr-2 h-4 w-4" /> 跟随系统{theme === "system" && " ✓"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 2: typecheck**

```bash
cd web && pnpm typecheck
```

Expected: 0 errors。

- [ ] **Step 3: 提交**

```bash
git add web/src/components/app-shell/ThemeToggle.tsx
git commit -m "feat(web): ThemeToggle dropdown (light/dark/system)"
```

---

### Task 0.11: UserMenu（头像 + 退出 + 角色）

**Files:**
- Create: `web/src/components/app-shell/UserMenu.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/UserMenu.tsx`：

```tsx
import { LogOut, User } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useStaffSession } from "@/hooks/useStaffSession";

export function UserMenu() {
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  const initial = role ? role[0].toUpperCase() : "?";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="账号菜单">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="text-xs">{initial}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          <User className="mr-2 inline h-3 w-3" />角色：{role ?? "(未登录)"}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => {
            logout();
            nav("/staff/login");
          }}
        >
          <LogOut className="mr-2 h-4 w-4" /> 退出
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/components/app-shell/UserMenu.tsx
git commit -m "feat(web): UserMenu (avatar dropdown with role + logout)"
```

---

### Task 0.12: Breadcrumbs 面包屑

**Files:**
- Create: `web/src/components/app-shell/Breadcrumbs.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/Breadcrumbs.tsx`：

```tsx
import { useLocation } from "react-router-dom";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { NAV_GROUPS } from "./nav-config";

/** 用 pathname 在 NAV_GROUPS 中查询当前页所在分组与标题。 */
function resolveCrumb(pathname: string): { group: string; page: string } | null {
  for (const g of NAV_GROUPS) {
    const item = g.items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
    if (item) return { group: g.label, page: item.label };
  }
  return null;
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumb = resolveCrumb(pathname);
  if (!crumb) return null;
  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem className="hidden md:block">
          <BreadcrumbLink className="text-muted-foreground">{crumb.group}</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator className="hidden md:block" />
        <BreadcrumbItem>
          <BreadcrumbPage>{crumb.page}</BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/components/app-shell/Breadcrumbs.tsx
git commit -m "feat(web): Breadcrumbs (resolve from NAV_GROUPS)"
```

---

### Task 0.13: CommandPalette ⌘K

**Files:**
- Create: `web/src/components/app-shell/CommandPalette.tsx`
- Create: `web/tests/commandPalette.test.tsx`

- [ ] **Step 1: 写测试**

写到 `web/tests/commandPalette.test.tsx`：

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CommandPalette } from "@/components/app-shell/CommandPalette";

vi.mock("@/hooks/useStaffSession", () => ({
  useStaffSession: () => ({ role: "admin" }),
}));
vi.mock("@/hooks/useDynamicMenu", () => ({ useDynamicMenu: () => ({ matrix: null }) }));

describe("CommandPalette", () => {
  it("⌘K 打开面板", () => {
    render(
      <MemoryRouter>
        <CommandPalette />
      </MemoryRouter>,
    );
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText(/搜索菜单/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试 FAIL**

```bash
cd web && pnpm vitest run tests/commandPalette.test.tsx
```

Expected: FAIL。

- [ ] **Step 3: 实现**

写到 `web/src/components/app-shell/CommandPalette.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList,
} from "@/components/ui/command";
import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useStaffSession } from "@/hooks/useStaffSession";
import { NAV_GROUPS, type NavItem } from "./nav-config";
import { PATH_TO_PERM } from "./perm-map";

function canAccess(item: NavItem, role: string | null, matrix: ReturnType<typeof useDynamicMenu>["matrix"]): boolean {
  const permKey = PATH_TO_PERM[item.to];
  if (matrix && permKey && role) return matrix.matrix[role]?.[permKey] === true;
  return !item.roles || (role != null && item.roles.includes(role));
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="搜索菜单…" />
      <CommandList>
        <CommandEmpty>未找到匹配项</CommandEmpty>
        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((i) => canAccess(i, role, matrix));
          if (visible.length === 0) return null;
          return (
            <CommandGroup key={group.id} heading={group.label}>
              {visible.map((item) => (
                <CommandItem
                  key={item.to}
                  value={`${group.label} ${item.label}`}
                  onSelect={() => {
                    setOpen(false);
                    nav(item.to);
                  }}
                >
                  <item.icon className="mr-2 h-4 w-4" />
                  {item.label}
                </CommandItem>
              ))}
            </CommandGroup>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}
```

- [ ] **Step 4: 测试通过**

```bash
cd web && pnpm vitest run tests/commandPalette.test.tsx
```

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/components/app-shell/CommandPalette.tsx web/tests/commandPalette.test.tsx
git commit -m "feat(web): CommandPalette (⌘K menu jump + RBAC filter)"
```

---

### Task 0.14: MobileSidebar（Sheet 抽屉）

**Files:**
- Create: `web/src/components/app-shell/MobileSidebar.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/MobileSidebar.tsx`：

```tsx
import { Menu } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { AppSidebar } from "./AppSidebar";

/** < md 时显示。点汉堡按钮打开 Sheet，Sheet 内复用 AppSidebar（强制显示）。 */
export function MobileSidebar() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="打开菜单">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <div className="!flex h-full" onClick={() => setOpen(false)}>
          {/* AppSidebar 自带 hidden md:flex，这里包一层强制显示 */}
          <div className="flex h-full w-full [&_aside]:!flex">
            <AppSidebar />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/components/app-shell/MobileSidebar.tsx
git commit -m "feat(web): MobileSidebar (Sheet wrapping AppSidebar for <md)"
```

---

### Task 0.15: AppTopbar

**Files:**
- Create: `web/src/components/app-shell/AppTopbar.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/AppTopbar.tsx`：

```tsx
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPalette } from "./CommandPalette";
import { MobileSidebar } from "./MobileSidebar";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

export function AppTopbar() {
  const [hint, setHint] = useState("⌘K");
  useEffect(() => {
    if (!navigator.userAgent.includes("Mac")) setHint("Ctrl+K");
  }, []);
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background px-3 md:px-4">
      <MobileSidebar />
      <div className="flex-1">
        <Breadcrumbs />
      </div>
      <Button
        variant="outline"
        size="sm"
        className="hidden gap-2 text-muted-foreground md:flex"
        onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
      >
        <Search className="h-3.5 w-3.5" />
        搜索菜单
        <kbd className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px]">{hint}</kbd>
      </Button>
      <ThemeToggle />
      <UserMenu />
      <CommandPalette />
    </header>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/components/app-shell/AppTopbar.tsx
git commit -m "feat(web): AppTopbar (breadcrumb + search + theme + user)"
```

---

### Task 0.16: AppShell 总壳

**Files:**
- Create: `web/src/components/app-shell/AppShell.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/components/app-shell/AppShell.tsx`：

```tsx
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { useStaffPresenceHeartbeat } from "@/hooks/useStaffPresenceHeartbeat";
import { useStaffSession } from "@/hooks/useStaffSession";
import { ThemeProvider } from "@/providers/ThemeProvider";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { NAV_GROUPS, APP_BRAND_NAME } from "./nav-config";

/** 浏览器 title：{页面名} · {品牌}。 */
function useDocTitle(pathname: string) {
  for (const g of NAV_GROUPS) {
    const item = g.items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
    if (item) {
      document.title = `${item.label} · ${APP_BRAND_NAME}`;
      return;
    }
  }
  document.title = APP_BRAND_NAME;
}

export function AppShell() {
  const { token } = useStaffSession();
  const { pathname } = useLocation();
  useStaffPresenceHeartbeat();
  useDocTitle(pathname);

  if (!token) return <Navigate to="/staff/login" replace />;

  return (
    <ThemeProvider>
      <div className="flex h-screen bg-background text-foreground">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopbar />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
        <Toaster richColors closeButton />
      </div>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/components/app-shell/AppShell.tsx
git commit -m "feat(web): AppShell (sidebar + topbar + Toaster + ThemeProvider)"
```

---

### Task 0.17: ForbiddenRoute 403 占位页

**Files:**
- Create: `web/src/routes/ForbiddenRoute.tsx`

- [ ] **Step 1: 实现**

写到 `web/src/routes/ForbiddenRoute.tsx`：

```tsx
import { Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function ForbiddenRoute() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <Lock className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-lg font-semibold">403 · 无权限</h1>
      <p className="text-sm text-muted-foreground">您当前角色无法访问此页面</p>
      <Button asChild variant="outline" size="sm">
        <Link to="/staff/conversations">返回工作台</Link>
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add web/src/routes/ForbiddenRoute.tsx
git commit -m "feat(web): ForbiddenRoute 403 placeholder"
```

---

### Task 0.18: App.tsx 切换到 AppShell + ChatRoute dark 兜底

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/routes/ChatRoute.tsx`（仅加一句副作用）

- [ ] **Step 1: 改 App.tsx**

打开 `web/src/App.tsx`，替换：

```tsx
import { StaffLayout } from "./components/StaffLayout";
```

为：

```tsx
import { AppShell } from "./components/app-shell/AppShell";
import { ForbiddenRoute } from "./routes/ForbiddenRoute";
```

替换：

```tsx
<Route element={<StaffLayout />}>
```

为：

```tsx
<Route element={<AppShell />}>
```

在该 `<Route element={<AppShell />}>` 块内最后追加：

```tsx
<Route path="/403" element={<ForbiddenRoute />} />
```

- [ ] **Step 2: ChatRoute 强制亮色**

打开 `web/src/routes/ChatRoute.tsx`，在组件顶部 `useEffect` 中（若没有，新增）加：

```tsx
import { useEffect } from "react";
// ...
useEffect(() => {
  document.documentElement.classList.remove("dark");
}, []);
```

- [ ] **Step 3: 跑 dev 服务器手动验证**

```bash
cd web && pnpm dev
```

打开 `http://localhost:5173/staff/conversations`（先登录 `/staff/login`），检查：
- 左侧 5 分组 Sidebar 出现
- Topbar 含面包屑/搜索按钮/主题切换/头像
- 主题切换三档可切（light/dark/system）
- ⌘K（Mac）/ Ctrl+K（其他）打开 CommandPalette，输入"会话"能跳到 `/staff/conversations`
- 折叠某组、刷新页面、折叠状态被记住
- 打开 `/` ChatRoute，确认 UI 与 main 分支一致（无暗色干扰）

- [ ] **Step 4: 跑全套测试**

```bash
cd web && pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build
```

Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add web/src/App.tsx web/src/routes/ChatRoute.tsx
git commit -m "feat(web): mount AppShell in App.tsx + ChatRoute dark fallback"
```

---

### Task 0.19: Phase 0 PR

- [ ] **Step 1: 推分支建 PR**

```bash
git push -u origin feat/admin-shadcn-phase-0
gh pr create --title "feat(web): admin-shadcn Phase 0 — AppShell 基建" --body "$(cat <<'EOF'
## 范围
- 加 shadcn-admin 依赖（@tanstack/react-table / react-hook-form / zod / sonner / cmdk / recharts 等）
- 接入 shadcn CSS 变量（亮/暗双主题）与 \`@/*\` 别名
- 新 AppShell：5 分组可折叠 Sidebar + Topbar（面包屑 / 搜索按钮 / 主题切换 / 头像菜单）+ CommandPalette ⌘K
- 替换 StaffLayout（旧文件保留，Phase 5 删）
- 403 占位页
- ChatRoute 强制亮色（不受主题切换影响）

## 不在范围
- 业务页面内部 UI（仍是旧组件，下一 Phase 起逐页迁）
- ChatRoute（C 端 webview）

## 测试
- 新增 vitest：theme / sidebarCollapsed / appSidebar / commandPalette
- 全套：typecheck / lint / test:ci / build 全绿
- 手动：5 分组在 admin 角色下全部可见、折叠记忆、主题切换三档、⌘K 跳转、ChatRoute 亮色不变

## 风险
ChatRoute 不动验证：Phase 0 合并后立刻在 APP webview 内打开 \`/\` 跑一遍。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: 等 review 合并**

---

# Phase 1: 列表类页面（12 页）

**目标：** 12 个列表型管理页全部用通用 `DataTable` + `Sheet` 抽屉重写。每 2-3 页一个独立 PR。

**分支：** `feat/admin-shadcn-phase-1-<batch>`（按批次）

---

### Task 1.0: 通用 DataTable 抽出

**Files:**
- Create: `web/src/components/admin/data-table/DataTable.tsx`
- Create: `web/src/components/admin/data-table/DataTableToolbar.tsx`
- Create: `web/src/components/admin/data-table/DataTableColumnHeader.tsx`
- Create: `web/src/components/admin/data-table/DataTablePagination.tsx`
- Create: `web/tests/dataTable.test.tsx`

- [ ] **Step 1: 写测试**

写到 `web/tests/dataTable.test.tsx`：

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/admin/data-table/DataTable";

type Row = { id: number; name: string };
const cols: ColumnDef<Row>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "name", header: "Name" },
];
const data: Row[] = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, name: `n${i}` }));

describe("DataTable", () => {
  it("渲染 + 默认分页 10 条", () => {
    render(<DataTable columns={cols} data={data} />);
    expect(screen.getByText("ID")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10);
  });

  it("翻页", () => {
    render(<DataTable columns={cols} data={data} />);
    fireEvent.click(screen.getByLabelText("下一页"));
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10);
    expect(screen.queryByText("n0")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑 FAIL**

```bash
cd web && pnpm vitest run tests/dataTable.test.tsx
```

- [ ] **Step 3: 实现 DataTable**

写到 `web/src/components/admin/data-table/DataTable.tsx`：

```tsx
import {
  ColumnDef, flexRender, getCoreRowModel,
  getFilteredRowModel, getPaginationRowModel, getSortedRowModel,
  SortingState, useReactTable, type Table as TanTable,
} from "@tanstack/react-table";
import { useState } from "react";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { DataTablePagination } from "./DataTablePagination";

export interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  toolbar?: (table: TanTable<TData>) => React.ReactNode;
  empty?: React.ReactNode;
}

export function DataTable<TData, TValue>({ columns, data, toolbar, empty }: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <div className="space-y-3">
      {toolbar?.(table)}
      <div className="rounded-md border border-border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead key={h.id}>
                    {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((c) => (
                    <TableCell key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  {empty ?? "暂无数据"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <DataTablePagination table={table} />
    </div>
  );
}
```

写到 `web/src/components/admin/data-table/DataTablePagination.tsx`：

```tsx
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import type { Table } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export function DataTablePagination<TData>({ table }: { table: Table<TData> }) {
  return (
    <div className="flex items-center justify-between px-2">
      <div className="text-xs text-muted-foreground">
        共 {table.getFilteredRowModel().rows.length} 条
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs">每页</span>
          <Select
            value={`${table.getState().pagination.pageSize}`}
            onValueChange={(v) => table.setPageSize(Number(v))}
          >
            <SelectTrigger className="h-7 w-[70px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[10, 20, 50, 100].map((p) => (
                <SelectItem key={p} value={`${p}`}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="text-xs">
          {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
        </div>
        <div className="flex gap-1">
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()} aria-label="首页">
            <ChevronsLeft className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label="上一页">
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label="下一页">
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()} aria-label="末页">
            <ChevronsRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
```

写到 `web/src/components/admin/data-table/DataTableColumnHeader.tsx`：

```tsx
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { Column } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DataTableColumnHeader<TData>({
  column, title, className,
}: {
  column: Column<TData, unknown>;
  title: string;
  className?: string;
}) {
  if (!column.getCanSort()) return <div className={className}>{title}</div>;
  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn("-ml-3 h-8 data-[state=open]:bg-accent", className)}
      onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
    >
      <span>{title}</span>
      {column.getIsSorted() === "asc" ? <ArrowUp className="ml-2 h-3 w-3" />
       : column.getIsSorted() === "desc" ? <ArrowDown className="ml-2 h-3 w-3" />
       : <ChevronsUpDown className="ml-2 h-3 w-3" />}
    </Button>
  );
}
```

写到 `web/src/components/admin/data-table/DataTableToolbar.tsx`：

```tsx
import { X } from "lucide-react";
import type { Table } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function DataTableToolbar<TData>({
  table, searchColumn, placeholder = "搜索…",
  children,
}: {
  table: Table<TData>;
  searchColumn?: string;
  placeholder?: string;
  children?: React.ReactNode;
}) {
  const filterColumn = searchColumn ? table.getColumn(searchColumn) : null;
  const isFiltered = table.getState().columnFilters.length > 0;
  return (
    <div className="flex items-center gap-2">
      {filterColumn && (
        <Input
          placeholder={placeholder}
          value={(filterColumn.getFilterValue() as string) ?? ""}
          onChange={(e) => filterColumn.setFilterValue(e.target.value)}
          className="h-8 w-[200px]"
        />
      )}
      {children}
      {isFiltered && (
        <Button variant="ghost" size="sm" onClick={() => table.resetColumnFilters()}>
          清除 <X className="ml-1 h-3 w-3" />
        </Button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 测试通过**

```bash
cd web && pnpm vitest run tests/dataTable.test.tsx
```

Expected: 2 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/components/admin/data-table/ web/tests/dataTable.test.tsx
git commit -m "feat(web): generic DataTable + Toolbar + Pagination"
```

---

## Phase 1 单页重写模板（每页对照此模板，按本节后续表逐页执行）

**每页 Task 套路：**

1. **读旧页**：`web/src/routes/admin/{Page}Route.tsx`
2. **识别**：表格数据源（哪个 `adminXxx.ts` API）、行字段、行操作、创建/编辑表单字段
3. **重写步骤**：
   - 顶部 PageHeader（保留原标题/描述，actions 区放新建按钮）
   - 列定义 `columns: ColumnDef<Row>[]`，行操作列尾部加 `<DropdownMenu>`（编辑/删除）
   - 用 `<DataTable columns={...} data={...} toolbar={(t) => <DataTableToolbar table={t} searchColumn="name" />} />`
   - 创建/编辑用 `<Sheet>`，表单用 `react-hook-form` + `zodResolver`，字段用 shadcn `<Form><FormField>` 系列
   - 提交结果 `toast.success(...)` / `toast.error(...)`（从 `sonner` 导入）
4. **typecheck + 跑该页相关测试**
5. **手动验证**：dev 启动后打开页面，覆盖创建/编辑/删除/翻页/搜索
6. **提交**：每页一个 commit；每 2-3 页一个 PR

**通用 import 模板：**

```tsx
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { MoreHorizontal, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { DataTable } from "@/components/admin/data-table/DataTable";
import { DataTableToolbar } from "@/components/admin/data-table/DataTableToolbar";
import { DataTableColumnHeader } from "@/components/admin/data-table/DataTableColumnHeader";
```

---

### Task 1.1: 重写 `/admin/staff-groups`（StaffGroupsRoute）

**Files:**
- Modify: `web/src/routes/admin/StaffGroupsRoute.tsx`（按上方模板重写）

**Row 字段：** `id` `name` `description` `active` `created_at`（来源 `adminStaffGroups.ts:StaffGroup`）
**行操作：** 编辑、删除
**表单字段：** `name`（必填）+ `description`（可选）
**API：** `listGroups` / `createGroup` / `patchGroup` / `deleteGroup`（已存在）

- [ ] **Step 1: 重写**（按上方模板）
- [ ] **Step 2: typecheck + 已有相关测试通过**

```bash
cd web && pnpm typecheck && pnpm vitest run
```

- [ ] **Step 3: 手动验证**（dev 启动后访问 `/admin/staff-groups`，过创建/编辑/删除/翻页）
- [ ] **Step 4: 提交**

```bash
git add web/src/routes/admin/StaffGroupsRoute.tsx
git commit -m "feat(web): rewrite /admin/staff-groups with DataTable + Sheet"
```

---

### Task 1.2-1.12: 重写其余 11 个列表页

每个 Task 按 1.1 同样套路。下表给出每页的关键参数。**每页一个 commit。每完成 2-3 页时建一个独立 PR。**

| Task | 路由 | API 模块 | Row 关键字段 | 表单字段 | 备注 |
|---|---|---|---|---|---|
| 1.2 | `/admin/staff` | `adminStaff.ts` | staff_id, display_name, role, group_id, skills, active | staff_id / display_name / role / password（创建）；display_name / role / group_id / skills / active（编辑） | 行操作含"重置密码"（额外 Dialog） |
| 1.3 | `/admin/rbac` | `adminRbac.ts` | 角色 x 权限的二维 matrix | 复选矩阵 | 不是常规 DataTable；保留现有 matrix UI 形态，外壳套 Page + Card，CTA 按钮换 shadcn |
| 1.4 | `/admin/shifts` | `adminShifts.ts` | Step 1 读 `ShiftsRoute.tsx` 识别 | 按 Step 1 字段等价 | 列表 + Sheet 编辑 |
| 1.5 | `/admin/presence` | `adminPresence.ts` | 在线状态心跳明细 | 仅查询，无 CUD | 顶部时间范围 + DataTable |
| 1.6 | `/admin/routing` | `adminRoutingRules.ts` | 路由规则 priority/condition/target | priority / condition / target | 优先级排序拖拽暂保留为数字字段（YAGNI） |
| 1.7 | `/admin/guardrails` | `adminGuardrails.ts` | Step 1 读 `GuardrailsRoute.tsx` 识别 | 按 Step 1 字段等价 | |
| 1.8 | `/admin/tools` | `adminToolPolicies.ts` | 工具策略 tool_name / role / allow | tool_name / role / allow | |
| 1.9 | `/admin/reports` | `adminReports.ts` | 自定义报表 | 查询条件 + 结果表 | 含 CSV 下载按钮 |
| 1.10 | `/admin/knowledge` | `adminKnowledge.ts` | 知识库条目 | 内容富文本暂用 `<Textarea>`（不引富文本编辑器） | |
| 1.11 | `/admin/audit` | `adminAudit.ts` | 操作审计日志 | 仅查询 | 时间倒序，顶部筛选 chips |
| 1.12 | `/admin/qa` | `adminQa.ts` | Step 1 读 `QaReviewRoute.tsx` 识别 | 按 Step 1 字段等价 | 含详情链接 → Phase 3 |

每个 Task 步骤一致：

- [ ] **Step 1: 重写**
- [ ] **Step 2: typecheck + 测试**
- [ ] **Step 3: 手动验证**
- [ ] **Step 4: 提交**（commit message 模式：`feat(web): rewrite /admin/xxx with DataTable + Sheet`）

**PR 批次建议：**
- Phase 1-batch-A：1.0 + 1.1 + 1.2 + 1.3（基建 + staff-groups/staff/rbac）
- Phase 1-batch-B：1.4 + 1.5 + 1.6（shifts/presence/routing）
- Phase 1-batch-C：1.7 + 1.8 + 1.9（guardrails/tools/reports）
- Phase 1-batch-D：1.10 + 1.11 + 1.12（knowledge/audit/qa）

每个 batch PR title: `feat(web): admin-shadcn Phase 1-<batch> — <pages>`

---

# Phase 2: 看板类（5 页）

**目标：** dashboard / sla / cost / performance / kpi 用统一 `KpiCard` + `recharts` 重写。

**分支：** `feat/admin-shadcn-phase-2`

---

### Task 2.0: KpiCard 通用组件

**Files:**
- Create: `web/src/components/admin/KpiCard.tsx`
- Create: `web/tests/kpiCard.test.tsx`

- [ ] **Step 1: 写测试**

```tsx
// web/tests/kpiCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { KpiCard } from "@/components/admin/KpiCard";

describe("KpiCard", () => {
  it("渲染 label / value / delta", () => {
    render(<KpiCard label="今日会话" value="1,234" delta="+12.3%" trend="up" />);
    expect(screen.getByText("今日会话")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("+12.3%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: FAIL**

```bash
cd web && pnpm vitest run tests/kpiCard.test.tsx
```

- [ ] **Step 3: 实现**

```tsx
// web/src/components/admin/KpiCard.tsx
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label, value, delta, trend = "flat", icon: Icon,
}: {
  label: string;
  value: string | number;
  delta?: string;
  trend?: "up" | "down" | "flat";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const TrendIcon = trend === "up" ? ArrowUp : trend === "down" ? ArrowDown : Minus;
  const trendCls = trend === "up" ? "text-emerald-600 dark:text-emerald-500"
                 : trend === "down" ? "text-rose-600 dark:text-rose-500"
                 : "text-muted-foreground";
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {delta && (
          <div className={cn("mt-1 flex items-center gap-1 text-xs", trendCls)}>
            <TrendIcon className="h-3 w-3" />
            {delta}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: PASS**

```bash
cd web && pnpm vitest run tests/kpiCard.test.tsx
```

- [ ] **Step 5: 提交**

```bash
git add web/src/components/admin/KpiCard.tsx web/tests/kpiCard.test.tsx
git commit -m "feat(web): KpiCard component"
```

---

### Task 2.1-2.5: 重写 5 个看板页

| Task | 路由 | 关键内容 |
|---|---|---|
| 2.1 | `/admin/dashboard` | 顶部时间范围 `<DatePicker>` 双选 → 4-5 张 KpiCard（今日会话/AI 解决率/人工接管/平均时长/SLA 达标率）→ recharts `LineChart` 趋势 + `BarChart` 分维度 |
| 2.2 | `/admin/sla` | SLA 阈值列表（DataTable）+ 达标率 KpiCard + 趋势 LineChart |
| 2.3 | `/admin/cost` | 成本 KpiCard（今日 token / API 费用 / 模型分布）+ recharts BarChart 按模型 |
| 2.4 | `/admin/performance` | 团队总览：KpiCard + 客服绩效 DataTable（行点击进 Phase 3 详情页） |
| 2.5 | `/staff/kpi` | 单客服 KPI：KpiCard 个人 + 趋势 LineChart |

**每页步骤：**

- [ ] **Step 1: 用模板重写**

公共结构示意：

```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { KpiCard } from "@/components/admin/KpiCard";
import { DatePicker } from "@/components/ui/date-picker";

export function DashboardRoute() {
  // ...拉数据
  return (
    <div className="space-y-4 p-4 md:p-6">
      {/* PageHeader */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">数据大盘</h1>
          <p className="text-sm text-muted-foreground">实时业务指标与趋势</p>
        </div>
        <div className="flex gap-2">
          <DatePicker date={from} onChange={setFrom} placeholder="起" />
          <DatePicker date={to} onChange={setTo} placeholder="止" />
        </div>
      </div>
      {/* KPI grid */}
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="今日会话" value={data.conv_today} delta="+12%" trend="up" />
        {/* ... */}
      </div>
      {/* Chart */}
      <div className="rounded-md border border-border bg-card p-4">
        <h3 className="mb-3 text-sm font-medium">会话趋势（近 30 天）</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.trend}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" className="text-xs" />
            <YAxis className="text-xs" />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: typecheck + 测试**
- [ ] **Step 3: 手动验证**（两个主题切换图表颜色不穿帮）
- [ ] **Step 4: 提交**（`feat(web): rewrite /admin/<page> with KpiCard + recharts`）

最后一个看板页完成后建 Phase 2 PR：

```bash
git push -u origin feat/admin-shadcn-phase-2
gh pr create --title "feat(web): admin-shadcn Phase 2 — 看板类（5 页）"
```

---

# Phase 3: 详情类（4 页）

**目标：** conversation logs / ticket detail / performance detail / prompt-editor 详情页用 `Breadcrumb` + `Tabs` 重写。

**分支：** `feat/admin-shadcn-phase-3`

---

### Task 3.1-3.4: 详情页重写

| Task | 路由 | Tabs 分组 | 关键内容 |
|---|---|---|---|
| 3.1 | `/staff/conversations/:id/logs` | 消息流 / 工具调用 / 反馈 | 卡片式时间倒序流 + 行操作 DropdownMenu |
| 3.2 | `/staff/tickets/:externalId` | 概览 / 事件流 / 关联会话 | Tabs + 事件流卡片 |
| 3.3 | `/admin/performance/:staffId` | 总览 KPI / 会话明细 / 质检结果 | KpiCard + Tabs + DataTable |
| 3.4 | `/admin/prompt-editor` | 草稿编辑器 / 历史版本 / 发布 | 左侧版本列表 + 右侧 `<Textarea>` 编辑器（不引 Monaco），保留现有发布/草稿 API 逻辑 |

**通用模板：**

```tsx
import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

export function TicketDetailRoute() {
  // ...
  return (
    <div className="space-y-4 p-4 md:p-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem><BreadcrumbLink asChild><Link to="/staff/tickets">工单</Link></BreadcrumbLink></BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem><BreadcrumbPage>{externalId}</BreadcrumbPage></BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild><Link to="/staff/tickets"><ArrowLeft className="mr-1 h-3 w-3" />返回</Link></Button>
      </div>
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="events">事件流</TabsTrigger>
          <TabsTrigger value="related">关联会话</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">{/* ... */}</TabsContent>
        <TabsContent value="events">{/* ... */}</TabsContent>
        <TabsContent value="related">{/* ... */}</TabsContent>
      </Tabs>
    </div>
  );
}
```

每页步骤：
- [ ] **Step 1: 重写**
- [ ] **Step 2: typecheck + 测试**
- [ ] **Step 3: 手动验证**
- [ ] **Step 4: 提交**（`feat(web): rewrite <page> with Tabs + Breadcrumb`）

Phase 3 PR：

```bash
git push -u origin feat/admin-shadcn-phase-3
gh pr create --title "feat(web): admin-shadcn Phase 3 — 详情类（4 页）"
```

---

# Phase 4: 工作台 SSE（5 页）

**目标：** conversations / tickets / spectate / insights / audits + ChatWindow 周边外壳重写。**SSE 订阅、状态机、消息流逻辑零改动**。

**分支：** `feat/admin-shadcn-phase-4`

⚠️ 此 Phase 风险最高。单 PR，严格 review，不混合其他改动。

---

### Task 4.1: `/staff/conversations` 列表

**Files:**
- Modify: `web/src/routes/staff/ConversationsListRoute.tsx`

- [ ] **Step 1: 重写外壳**

PageHeader + 过滤 chips（status/assigned_to_me）+ DataTable（按需保留无限滚动则用 cursor 模式，否则普通分页）。

⚠️ **不改：** SSE `useEffect` 订阅、`new EventSource(...)` 连接、消息缓存 ref、自动滚动逻辑。仅替换 wrapper 节点。

- [ ] **Step 2: typecheck + 跑原有 `tests/staff.test.tsx` `tests/spectate.test.tsx` 等**
- [ ] **Step 3: 手动验证 SSE：** 启动后让别人发起新会话，确认列表实时更新；切到其他页再回来，订阅恢复
- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/ConversationsListRoute.tsx
git commit -m "feat(web): rewrite /staff/conversations outer shell (SSE intact)"
```

---

### Task 4.2: `/staff/conversations/:id` 详情（接管对话页）

**Files:**
- Modify: `web/src/routes/staff/ConversationDetailRoute.tsx`
- Modify: `web/src/components/ChatWindow.tsx`（仅样式 className，不动状态机）
- Modify: `web/src/components/MessageList.tsx`
- Modify: `web/src/components/MessageBubble.tsx`
- Modify: `web/src/components/InputBox.tsx`
- Modify: `web/src/components/AiDraftPanel.tsx`
- Modify: `web/src/components/AiToolsPanel.tsx`
- Modify: `web/src/components/TakeoverFooter.tsx`
- Modify: `web/src/components/HandoffButton.tsx`

⚠️ **绝对禁止：**
- 改 `useChat` / `useEffect` SSE 订阅块
- 改 message 缓存 ref / 闭包局部变量逻辑（避开 StrictMode 双订阅问题，见项目记忆 `chat-event-driven-no-optimistic`）
- 改 client_message_id 生成 / 重发逻辑
- 加本地乐观 push

仅允许：
- className 替换（`bg-brand` → `bg-primary` 等）
- 布局容器换成 shadcn `<Card>` / `<ScrollArea>` / `<Tabs>`
- 按钮换 `<Button>`
- 提示替换为 `sonner` toast

- [ ] **Step 1: 重写三栏布局**（左会话上下文 / 中对话区 / 右 AI 工具/草稿面板）
- [ ] **Step 2: typecheck + 跑原有 `tests/ChatWindow.test.tsx` `tests/staff.test.tsx` `tests/aiDraft.test.tsx` `tests/staffAttach.test.tsx`**
- [ ] **Step 3: 手动验证：**
  - 用户发消息 → 实时显示
  - 接管 / 释放 / 解决 / 转派 全链路
  - AI 草稿 enable/disable/approve/reject
  - 工具调用面板正常显示
  - StrictMode dev 下不丢消息
- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/ConversationDetailRoute.tsx web/src/components/*.tsx
git commit -m "feat(web): rewrite conversation detail shell (SSE/state intact)"
```

---

### Task 4.3-4.5: 工单列表 / 旁观 / 知识缺口 / 工具审计

| Task | 路由 | 重写要点 |
|---|---|---|
| 4.3 | `/staff/tickets` | DataTable + 状态 Badge + 过滤 chips |
| 4.4 | `/staff/conversations/:id/spectate` | 全屏只读对话流，顶部 Topbar 退化为标题条 + 返回按钮（不套 AppShell） |
| 4.5 | `/staff/insights` + `/staff/audits` | DataTable + 过滤 chips |

每个 Task：
- [ ] **Step 1: 重写**
- [ ] **Step 2: typecheck + 测试（含 `spectate.test.tsx` / `staffLogs.test.tsx`）**
- [ ] **Step 3: 手动验证**
- [ ] **Step 4: 提交**

Phase 4 PR：

```bash
git push -u origin feat/admin-shadcn-phase-4
gh pr create --title "feat(web): admin-shadcn Phase 4 — 工作台 SSE（5 页）" --body "⚠️ SSE 逻辑零改动，仅外壳替换。手动验证清单：列表实时更新 / 接管释放 / AI 草稿 / 旁观全屏。"
```

---

# Phase 5: 清理

**目标：** 删除旧 `StaffLayout.tsx`、dead code、未使用的 token、未使用的 import。

**分支：** `feat/admin-shadcn-phase-5`

---

### Task 5.1: 删 StaffLayout 与相关 dead code

**Files:**
- Delete: `web/src/components/StaffLayout.tsx`
- Delete: `web/tests/staffLayout.test.tsx`
- Modify: `web/src/App.tsx`（确认无 import 残留）

- [ ] **Step 1: 删文件**

```bash
cd /Users/sunchenglin/codes/tevau-cs-engine
rm web/src/components/StaffLayout.tsx web/tests/staffLayout.test.tsx
```

- [ ] **Step 2: grep 任何残留 import**

```bash
grep -rn "StaffLayout" web/src web/tests 2>&1 | grep -v node_modules
```

Expected: 无输出。

- [ ] **Step 3: typecheck + lint + test + build**

```bash
cd web && pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build
```

Expected: 全绿。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore(web): remove obsolete StaffLayout"
```

---

### Task 5.2: 清理 tailwind config 与 globals.css

**Files:**
- Modify: `web/tailwind.config.ts`（仅当确认 brand/ink/surface/line 完全只剩 ChatRoute 用，且 ChatRoute 也不再用某些字号时才删）
- Modify: `web/src/styles/globals.css`（删 `.focus-glow` 等只服务 admin/staff 的工具类）

- [ ] **Step 1: 搜索每个自有 token 在 admin/staff 是否还有引用**

```bash
cd web
for token in "bg-brand" "text-ink-primary" "text-ink-secondary" "bg-surface-card" "border-line" "text-body1" "text-body2" "text-sh2"; do
  echo "=== $token ==="
  grep -rn "$token" src/routes/admin src/routes/staff src/components/app-shell 2>&1 | head -3
done
```

Expected: admin/staff 无引用。如有遗漏，回到 Phase 1-4 对应页清理。

- [ ] **Step 2: 删未用工具类**

仅删 admin/staff 已不引用的类。**ChatRoute 用的全部保留。**

- [ ] **Step 3: typecheck + lint + test + build**

```bash
cd web && pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build
```

- [ ] **Step 4: 手动 ChatRoute 全量回归**：在 APP webview 内打开 `/`，过完整对话流，确认 UI 与 Phase 0 合并前一致

- [ ] **Step 5: 提交**

```bash
git add web/tailwind.config.ts web/src/styles/globals.css
git commit -m "chore(web): cleanup unused tokens after admin/staff migration"
```

Phase 5 PR：

```bash
git push -u origin feat/admin-shadcn-phase-5
gh pr create --title "feat(web): admin-shadcn Phase 5 — 清理"
```

---

# 全部 Phase 完成验收清单

合并 Phase 5 后跑：

- [ ] `cd web && pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build` 全绿
- [ ] 用 agent / supervisor / admin 三种角色登录，逐项点开 5 分组下所有菜单，**每个页面**：
  - [ ] 数据正常加载
  - [ ] 创建/编辑/删除（如有）行为等价于 main
  - [ ] 亮/暗主题切换无穿帮
  - [ ] 桌面 ≥1280 + 移动 <768 两档可读
- [ ] ChatRoute 在 APP webview 内打开，UI 与 main 像素级一致
- [ ] BuLoginRoute / SpectateRoute 风格统一到新主题
- [ ] CommandPalette `⌘K` 能跳所有可见菜单
- [ ] Sidebar 分组折叠状态跨刷新保留
- [ ] 浏览器 title 按页面动态更新
- [ ] 无 console error / warning（dev mode 跑一遍）

---

## 风险与已记录的项目约定

1. **ChatRoute 守护**：所有 Phase 完成时跑 webview 回归。`document.documentElement.classList.remove("dark")` 兜底已在 Phase 0 加入。
2. **SSE 状态机零改动**：Phase 4 的硬规则，PR review 时按 diff 强制确认无 `useChat` / `useEffect` 订阅块改动。
3. **后端 docker 重建提醒**（项目记忆）：本计划纯前端改动，**无需** `docker compose up -d --build api`。
4. **Prompt 不动**：本计划与 prompt 版本无关，**无需**改 v1.0.0/v1.1.0 双版本。
5. **dev server 工作树检查**（项目记忆）：每个 Phase 验证前先 `ps aux | grep vite`，确认 dev server 跑在本工作树而非主仓库。
