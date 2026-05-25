# 全部界面统一重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/` 所有界面统一到现有品牌设计 token 之上，做视觉重塑 + 组件化，不改任何业务逻辑/数据流/路由/API。

**Architecture:** 先补全共享 `ui/` 组件库（Input/Textarea/Field/Alert/Badge/PageContainer/PageHeader/FilterTabs/Table 原语/EmptyState），再逐页把原生 `<input>/<table>/<button>` 与失效 token（`bg-fill-secondary`、默认色 `bg-yellow-50`）替换为这套组件与 token。每页改完跑类型检查 + 既有测试保持全绿。

**Tech Stack:** React 18 + Vite + TypeScript + TailwindCSS 3 + radix + cva + lucide-react + vitest/testing-library，包管理器 pnpm。所有命令在 `web/` 目录下执行。

**约束（全程遵守）:**
- 不改 `tailwind.config.ts` 的 token（除非某步骤显式说明）。
- 不改 hooks、`api/*`、路由路径、组件对外 props 契约。
- 既有测试 `web/tests/*` 必须保持全绿；下列文案/placeholder/aria-label 在重构后必须**逐字保留**：
  - 登录："工号""密码""登录"
  - 会话列表：`#{id}` 形式（测试断言 `/#9/`）
  - 会话详情："接管""已接管"
  - TakeoverFooter："回复用户…""发送""转派给 staff_id…""转派""标记已解决"
  - Spectate："AI：…""用户：…"（由 `label()` 生成，勿动该函数）
  - KPI："AG1"类 staff_id、"75%"（`toFixed(0)`）、"2分5秒"（`fmtDuration`）
  - Prompts："需要 admin 权限""v1.1.0"类版本名、"保存""已保存并热加载"、aria-label `${v} 灰度比例`
  - AiToolsPanel：aria-label "工具参数 JSON"
- `BuLoginRoute` 已被加入 `setIdentity({ kind: "b", buId })` 调用与 `../api/identity` 导入——重构时保留，勿删。

---

### Task 1: 补全共享 UI 组件库

**Files:**
- Create: `web/src/components/ui/input.tsx`
- Create: `web/src/components/ui/field.tsx`
- Create: `web/src/components/ui/alert.tsx`
- Create: `web/src/components/ui/badge.tsx`
- Create: `web/src/components/ui/page.tsx`
- Create: `web/src/components/ui/filter-tabs.tsx`
- Create: `web/src/components/ui/table.tsx`
- Create: `web/src/components/ui/empty-state.tsx`
- Test: `web/tests/ui.test.tsx`

- [ ] **Step 1: 写失败测试**

`web/tests/ui.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Alert } from "../src/components/ui/alert";
import { Badge } from "../src/components/ui/badge";
import { FilterTabs } from "../src/components/ui/filter-tabs";
import { Input } from "../src/components/ui/input";

describe("ui primitives", () => {
  it("Badge 渲染内容并按 variant 上色", () => {
    const { getByText } = render(<Badge variant="pending">待人工</Badge>);
    const el = getByText("待人工");
    expect(el.className).toContain("status-warning");
  });

  it("Alert 渲染内容", () => {
    const { getByText } = render(<Alert variant="error">出错了</Alert>);
    expect(getByText("出错了")).toBeInTheDocument();
  });

  it("Input 透传 placeholder 与 onChange", () => {
    const onChange = vi.fn();
    const { getByPlaceholderText } = render(<Input placeholder="工号" onChange={onChange} />);
    fireEvent.change(getByPlaceholderText("工号"), { target: { value: "x" } });
    expect(onChange).toHaveBeenCalled();
  });

  it("FilterTabs 点击触发 onChange，选中项高亮", () => {
    const onChange = vi.fn();
    const { getByText } = render(
      <FilterTabs
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "甲" },
          { value: "b", label: "乙" },
        ]}
      />,
    );
    expect(getByText("甲").className).toContain("bg-brand");
    fireEvent.click(getByText("乙"));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pnpm exec vitest run tests/ui.test.tsx`
Expected: FAIL，报找不到 `../src/components/ui/*` 模块。

- [ ] **Step 3: 实现各组件**

`web/src/components/ui/input.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

const base =
  "focus-glow w-full rounded border border-line bg-surface-card px-input-x py-3 " +
  "text-body1 text-ink-primary outline-none transition-all duration-250 " +
  "placeholder:text-ink-secondary disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...p }, ref) => <input ref={ref} className={cn(base, className)} {...p} />,
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(base, "resize-none", className)} {...p} />
));
Textarea.displayName = "Textarea";
```

`web/src/components/ui/field.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

export function Field({
  label,
  htmlFor,
  error,
  className,
  children,
}: {
  label?: string;
  htmlFor?: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-body3 text-ink-subtle">
          {label}
        </label>
      )}
      {children}
      {error && <span className="text-body4 text-status-error">{error}</span>}
    </div>
  );
}
```

`web/src/components/ui/alert.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

const variants = {
  info: "bg-surface-container text-ink-secondary",
  success: "bg-status-success/10 text-status-success",
  error: "bg-status-error/10 text-status-error",
} as const;

export function Alert({
  variant = "info",
  className,
  children,
}: {
  variant?: keyof typeof variants;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded px-3 py-2 text-body3", variants[variant], className)}>{children}</div>
  );
}
```

`web/src/components/ui/badge.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

const variants = {
  neutral: "bg-surface-container text-ink-secondary",
  pending: "bg-status-warning/15 text-status-warning",
  takeover: "bg-brand-tab text-ink-primary",
  success: "bg-status-success/15 text-status-success",
  error: "bg-status-error/15 text-status-error",
} as const;

export function Badge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: keyof typeof variants;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-0.5 text-body4",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
```

`web/src/components/ui/page.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

const widths = {
  default: "max-w-[720px]",
  form: "max-w-[560px]",
  narrow: "max-w-[420px]",
} as const;

export function PageContainer({
  width = "default",
  center = false,
  fullHeight = false,
  className,
  children,
}: {
  width?: keyof typeof widths;
  center?: boolean;
  fullHeight?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "mx-auto px-page py-block-lg",
        widths[width],
        (center || fullHeight) && "flex h-full flex-col",
        center && "justify-center",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  actions,
  className,
}: {
  title: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-center gap-2", className)}>
      <h2 className="flex-1 text-sh2 text-ink-primary">{title}</h2>
      {actions}
    </div>
  );
}
```

`web/src/components/ui/filter-tabs.tsx`:

```tsx
import { cn } from "../../lib/utils";

export function FilterTabs<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <div className={cn("flex gap-2", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded px-2 py-1 text-body3 transition-colors",
            value === o.value
              ? "bg-brand text-ink-primary"
              : "bg-surface-container text-ink-secondary hover:bg-surface-hover",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
```

`web/src/components/ui/table.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

export const Table = ({ className, ...p }: React.TableHTMLAttributes<HTMLTableElement>) => (
  <table className={cn("w-full text-body3", className)} {...p} />
);
export const THead = ({ className, ...p }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className={cn("text-left text-ink-secondary", className)} {...p} />
);
export const TBody = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <tbody {...p} />;
export const Tr = ({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn("border-t border-line text-ink-primary", className)} {...p} />
);
export const Th = ({ className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className={cn("py-2 font-normal", className)} {...p} />
);
export const Td = ({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className={cn("py-2", className)} {...p} />
);
```

`web/src/components/ui/empty-state.tsx`:

```tsx
import * as React from "react";

import { cn } from "../../lib/utils";

export function EmptyState({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("py-8 text-center text-body3 text-ink-secondary", className)}>{children}</div>
  );
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pnpm exec vitest run tests/ui.test.tsx`
Expected: PASS（4 个用例）。

- [ ] **Step 5: 类型检查 + 提交**

Run: `pnpm typecheck`
Expected: 无错误。

```bash
git add web/src/components/ui web/tests/ui.test.tsx
git commit -m "feat(web/ui): 补全共享 UI 组件库（Input/Field/Alert/Badge/Page/FilterTabs/Table/EmptyState）"
```

---

### Task 2: 重构登录页（BuLogin + StaffLogin）

**Files:**
- Modify: `web/src/routes/BuLoginRoute.tsx`
- Modify: `web/src/routes/staff/StaffLoginRoute.tsx`
- Test: `web/tests/staff.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/staff.test.tsx`
Expected: PASS（其中校验 placeholder "工号""密码" 与按钮 "登录"）。

- [ ] **Step 2: 重写 StaffLoginRoute**

`web/src/routes/staff/StaffLoginRoute.tsx`（保留全部逻辑，仅换展示层）:

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Field } from "../../components/ui/field";
import { Input } from "../../components/ui/input";
import { PageContainer } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";
import { staffLogin } from "../../api/staff";

export function StaffLoginRoute() {
  const [staffId, setStaffId] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useStaffSession();
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const { token } = await staffLogin(staffId.trim(), password);
      login(token);
      nav("/staff/conversations");
    } catch {
      setErr("工号或密码错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer width="narrow" center>
      <h2 className="mb-4 text-center text-sh1 text-ink-primary">客服工作台登录</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field>
          <Input
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            placeholder="工号"
          />
        </Field>
        <Field error={err}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
          />
        </Field>
        <Button type="submit" disabled={loading || !staffId.trim() || !password}>
          {loading ? "..." : "登录"}
        </Button>
      </form>
    </PageContainer>
  );
}
```

- [ ] **Step 3: 重写 BuLoginRoute**

`web/src/routes/BuLoginRoute.tsx`（保留 `setIdentity` 调用与 fetch 逻辑）:

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { setIdentity } from "../api/identity";
import { Button } from "../components/ui/button";
import { Field } from "../components/ui/field";
import { Input } from "../components/ui/input";
import { PageContainer } from "../components/ui/page";

/** B 端主账户 ID 登录页（spec §4.1）。 */
export function BuLoginRoute() {
  const [buId, setBuId] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const r = await fetch("/api/v1/auth/bu/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bu_id: buId.trim() }),
      });
      if (!r.ok) {
        setErr((await r.text()) || "主账户不存在或已禁用");
        return;
      }
      setIdentity({ kind: "b", buId: buId.trim() });
      nav("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer width="narrow" center>
      <div className="mb-4 text-center">
        <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded bg-brand">
          <span className="text-sh1 font-bold text-ink-primary">T</span>
        </div>
        <h2 className="text-sh1 text-ink-primary">Tevau AI 客服</h2>
        <p className="text-body3 text-ink-secondary">合作伙伴技术支持</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field error={err}>
          <Input
            value={buId}
            onChange={(e) => setBuId(e.target.value)}
            placeholder="主账户 ID（例如 BU00243780）"
          />
        </Field>
        <Button type="submit" disabled={loading || !buId.trim()}>
          {loading ? "..." : "进入对话"}
        </Button>
      </form>
    </PageContainer>
  );
}
```

> 注意：`setIdentity` 的 import 路径与签名以仓库当前 `web/src/api/identity.ts` 为准；若实际路径/字段名不同，按现有文件修正，勿改其行为。

- [ ] **Step 4: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/staff.test.tsx`
Expected: 均 PASS。

- [ ] **Step 5: 提交**

```bash
git add web/src/routes/BuLoginRoute.tsx web/src/routes/staff/StaffLoginRoute.tsx
git commit -m "refactor(web): 登录页统一为 PageContainer/Field/Input"
```

---

### Task 3: 重构 ConversationsListRoute

**Files:**
- Modify: `web/src/routes/staff/ConversationsListRoute.tsx`
- Test: `web/tests/staff.test.tsx`、`web/tests/multiStaff.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/staff.test.tsx tests/multiStaff.test.tsx`
Expected: PASS。

- [ ] **Step 2: 重写文件**

`web/src/routes/staff/ConversationsListRoute.tsx`（逻辑不变，展示层换组件）:

```tsx
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listStaffConversations, type StaffConversation } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

const FILTER_OPTIONS = [
  { value: "human_pending", label: "待人工" },
  { value: "human_takeover", label: "人工接管" },
  { value: "all", label: "全部" },
] as const;

export function ConversationsListRoute() {
  const { token, role, logout } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [items, setItems] = useState<StaffConversation[]>([]);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    listStaffConversations(token, status)
      .then(setItems)
      .catch(() => setErr("加载失败，请重新登录"));
  }, [token, status, nav]);

  return (
    <PageContainer>
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
      <FilterTabs
        className="mb-3"
        value={status}
        onChange={setStatus}
        options={FILTER_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
      />
      {err && <Alert variant="error" className="mb-3">{err}</Alert>}
      <ul className="flex flex-col gap-2">
        {items.map((c) => (
          <li key={c.id} className="flex items-center gap-2">
            <Card className="flex-1 transition-colors hover:bg-surface-hover">
              <Link to={`/staff/conversations/${c.id}`} className="block px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="flex-1 text-body1 text-ink-primary">
                    #{c.id} · {c.user_type === "c" ? "C 端用户" : "BU"} {c.subject_id}
                  </span>
                  <Badge variant="neutral">{c.mode}</Badge>
                </div>
              </Link>
            </Card>
            {canSpectate && (
              <Button asChild variant="ghost" size="sm">
                <Link to={`/staff/conversations/${c.id}/spectate`}>旁观</Link>
              </Button>
            )}
          </li>
        ))}
        {items.length === 0 && !err && <EmptyState>暂无会话</EmptyState>}
      </ul>
    </PageContainer>
  );
}
```

> `setStatus` 接收 string，`FilterTabs<T>` 推断 T 为 union；传入 `value={status}`（string）即可，`onChange={setStatus}` 类型兼容。若 TS 报 union 不匹配 string，将 `options` 的 `value` 断言为 `string`：`options={[{ value: "human_pending" as string, label: "待人工" }, ...]}`。

- [ ] **Step 3: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/staff.test.tsx tests/multiStaff.test.tsx`
Expected: 均 PASS（含 `/#9/` 断言）。

- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/ConversationsListRoute.tsx
git commit -m "refactor(web): 会话列表统一为 Card/Badge/FilterTabs/EmptyState"
```

---

### Task 4: 重构 KpiRoute

**Files:**
- Modify: `web/src/routes/staff/KpiRoute.tsx`
- Test: `web/tests/multiStaff.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/multiStaff.test.tsx`
Expected: PASS（断言 "AG1""75%""2分5秒"）。

- [ ] **Step 2: 重写文件**

`web/src/routes/staff/KpiRoute.tsx`（`fmtDuration` 与单元格内容/格式保持不变）:

```tsx
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getKpi, type StaffKpi } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Table, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useStaffSession } from "../../hooks/useStaffSession";

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

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

  return (
    <PageContainer>
      <PageHeader
        title="客服 KPI 看板"
        actions={
          <Button asChild variant="link" size="sm">
            <Link to="/staff/conversations">返回工作台</Link>
          </Button>
        }
      />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      <Table>
        <THead>
          <tr>
            <Th>客服</Th>
            <Th>接管</Th>
            <Th>解决</Th>
            <Th>释放回 AI</Th>
            <Th>解决率</Th>
            <Th>平均时长</Th>
          </tr>
        </THead>
        <TBody>
          {rows.map((r) => (
            <Tr key={r.staff_id}>
              <Td>{r.staff_id}</Td>
              <Td>{r.takeovers}</Td>
              <Td>{r.resolved}</Td>
              <Td>{r.releases}</Td>
              <Td>{(r.resolved_ratio * 100).toFixed(0)}%</Td>
              <Td>{fmtDuration(r.avg_handle_seconds)}</Td>
            </Tr>
          ))}
        </TBody>
      </Table>
      {rows.length === 0 && !err && <EmptyState>暂无数据</EmptyState>}
    </PageContainer>
  );
}
```

> 空态从原来的 `<tr><td colSpan>` 改为表格外的 `EmptyState`，行为等价（无数据时不渲染数据行）。

- [ ] **Step 3: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/multiStaff.test.tsx`
Expected: 均 PASS。

- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/KpiRoute.tsx
git commit -m "refactor(web): KPI 看板统一为 Table 原语 + EmptyState"
```

---

### Task 5: 重构客服侧面板组件（AiDraftPanel / AiToolsPanel / TakeoverFooter）

**Files:**
- Modify: `web/src/components/AiDraftPanel.tsx`
- Modify: `web/src/components/AiToolsPanel.tsx`
- Modify: `web/src/components/TakeoverFooter.tsx`
- Test: `web/tests/aiDraft.test.tsx`、`web/tests/aiTools.test.tsx`、`web/tests/multiStaff.test.tsx`（既有，保持绿）

这些组件对外 props 契约不变，仅替换原生控件与失效 token `bg-fill-secondary`（未定义）→ `bg-surface-subtle`。

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/aiDraft.test.tsx tests/aiTools.test.tsx tests/multiStaff.test.tsx`
Expected: PASS。

- [ ] **Step 2: 重写 AiDraftPanel**

`web/src/components/AiDraftPanel.tsx`:

```tsx
import { useEffect, useState } from "react";

import { Button } from "./ui/button";
import { Textarea } from "./ui/input";

type Props = {
  draft: string | null;
  onApprove: () => void | Promise<void>;
  onReject: (rewrite: string) => void | Promise<void>;
};

/** 客服 review AI 草稿：直接发出，或改写后发。 */
export function AiDraftPanel({ draft, onApprove, onReject }: Props) {
  const [rewrite, setRewrite] = useState("");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setRewrite(draft ?? "");
    setEditing(false);
  }, [draft]);

  if (draft === null) return null;

  return (
    <div className="mb-3 rounded border border-line bg-surface-subtle p-3">
      <div className="mb-1 text-footnote text-ink-secondary">AI 草稿（未发送）</div>
      {editing ? (
        <Textarea
          value={rewrite}
          onChange={(e) => setRewrite(e.target.value)}
          rows={4}
          className="text-body2"
        />
      ) : (
        <div className="whitespace-pre-wrap text-body2 text-ink-primary">{draft}</div>
      )}
      <div className="mt-2 flex gap-2">
        {editing ? (
          <Button size="sm" onClick={() => onReject(rewrite.trim())} disabled={!rewrite.trim()}>
            改写后发送
          </Button>
        ) : (
          <>
            <Button size="sm" onClick={() => onApprove()}>
              直接发出
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              改写
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 重写 AiToolsPanel**

`web/src/components/AiToolsPanel.tsx`（保留 aria-label "工具参数 JSON"，`<select>` 套用 token 样式）:

```tsx
import { useState } from "react";

import { runAiTool, type AiToolResult } from "../api/staff";
import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Textarea } from "./ui/input";

const TOOLS = ["query_user", "query_card", "query_api_call", "search_code", "lookup_api_doc"];

type Props = {
  token: string;
  convId: number;
};

/** 客服上下文工具面板：代查 AI 工具，结果只在面板显示、不进对话流。 */
export function AiToolsPanel({ token, convId }: Props) {
  const [tool, setTool] = useState(TOOLS[0]);
  const [paramsText, setParamsText] = useState("{}");
  const [result, setResult] = useState<AiToolResult | null>(null);
  const [err, setErr] = useState("");
  const [running, setRunning] = useState(false);

  async function run() {
    setErr("");
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(paramsText || "{}");
    } catch {
      setErr("参数不是合法 JSON");
      return;
    }
    setRunning(true);
    try {
      setResult(await runAiTool(token, convId, tool, params));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded border border-line bg-surface-card p-3">
      <div className="mb-2 text-footnote text-ink-secondary">代查工具（结果仅你可见）</div>
      <select
        value={tool}
        onChange={(e) => setTool(e.target.value)}
        className="focus-glow mb-2 w-full rounded border border-line bg-surface-card px-2 py-2 text-body2 outline-none transition-all duration-250"
      >
        {TOOLS.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <Textarea
        value={paramsText}
        onChange={(e) => setParamsText(e.target.value)}
        rows={3}
        aria-label="工具参数 JSON"
        className="mb-2 px-2 py-1 text-body3 font-mono"
      />
      <Button size="sm" onClick={run} disabled={running}>
        {running ? "查询中…" : "运行"}
      </Button>
      {err && (
        <Alert variant="error" className="mt-2">
          {err}
        </Alert>
      )}
      {result && (
        <pre className="mt-2 max-h-60 overflow-auto rounded bg-surface-subtle p-2 text-footnote">
          {result.ok ? JSON.stringify(result.data, null, 2) : `错误：${result.error}`}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 重写 TakeoverFooter**

`web/src/components/TakeoverFooter.tsx`（保留全部 placeholder/按钮文案与逻辑）:

```tsx
import { useState } from "react";

import {
  resolveConversation,
  sendStaffMessage,
  transferConversation,
  type StaffStreamEvent,
} from "../api/staff";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

type Props = {
  token: string;
  convId: number;
  onLocalEvent: (e: StaffStreamEvent) => void;
  onNotice: (msg: string) => void;
};

/** 接管后底部操作区：回复 / 转派 / 标记已解决。 */
export function TakeoverFooter({ token, convId, onLocalEvent, onNotice }: Props) {
  const [draft, setDraft] = useState("");
  const [target, setTarget] = useState("");

  async function send() {
    if (!draft.trim()) return;
    await sendStaffMessage(token, convId, draft.trim());
    onLocalEvent({ type: "human_message", content: draft.trim() });
    setDraft("");
  }

  async function transfer() {
    if (!target.trim()) return;
    const ok = await transferConversation(token, convId, target.trim());
    onNotice(ok ? `已转派给 ${target.trim()}` : "转派失败（权限或目标不存在）");
    setTarget("");
  }

  async function resolve() {
    await resolveConversation(token, convId);
    onNotice("已标记解决并释放回 AI");
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="回复用户…"
          className="flex-1 py-2"
        />
        <Button size="md" onClick={send} disabled={!draft.trim()}>
          发送
        </Button>
      </div>
      <div className="flex gap-2">
        <Input
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="转派给 staff_id…"
          className="flex-1 py-2 text-body3"
        />
        <Button size="sm" variant="ghost" onClick={transfer} disabled={!target.trim()}>
          转派
        </Button>
        <Button size="sm" variant="ghost" onClick={resolve}>
          标记已解决
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/aiDraft.test.tsx tests/aiTools.test.tsx tests/multiStaff.test.tsx`
Expected: 均 PASS。

- [ ] **Step 6: 提交**

```bash
git add web/src/components/AiDraftPanel.tsx web/src/components/AiToolsPanel.tsx web/src/components/TakeoverFooter.tsx
git commit -m "refactor(web): 客服侧面板统一为 Input/Textarea/Alert + 修复失效 token"
```

---

### Task 6: 重构 ConversationDetailRoute

**Files:**
- Modify: `web/src/routes/staff/ConversationDetailRoute.tsx`
- Test: `web/tests/staff.test.tsx`、`web/tests/multiStaff.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/staff.test.tsx tests/multiStaff.test.tsx`
Expected: PASS（断言 "接管""已接管"）。

- [ ] **Step 2: 重写文件**

`web/src/routes/staff/ConversationDetailRoute.tsx`（`useStaffStream` hook、所有事件逻辑保持不变；header 换 PageHeader，notice 换 Alert，EventLog 容器套用 Card）:

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  releaseConversation,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { TakeoverFooter } from "../../components/TakeoverFooter";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useAiDraft } from "../../hooks/useAiDraft";
import { useStaffSession } from "../../hooks/useStaffSession";

/** 订阅会话事件总线，返回累积的事件列表 + 追加器。 */
function useStaffStream(
  token: string | null,
  convId: number,
): [StaffStreamEvent[], (e: StaffStreamEvent) => void] {
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  const stopped = useRef(false);
  useEffect(() => {
    if (!token) return;
    stopped.current = false;
    (async () => {
      try {
        for await (const ev of streamStaffEvents(token, convId)) {
          if (stopped.current) break;
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        /* 流断开，忽略 */
      }
    })();
    return () => {
      stopped.current = true;
    };
  }, [token, convId]);
  return [events, (e) => setEvents((prev) => [...prev, e])];
}

function EventLog({ events }: { events: StaffStreamEvent[] }) {
  return (
    <ul className="mb-3 flex flex-1 flex-col gap-1 overflow-y-auto">
      {events.map((ev, i) => (
        <li key={i} className="text-body2 text-ink-primary">
          <span className="mr-1 text-footnote text-ink-secondary">[{ev.type}]</span>
          {ev.content ?? ev.to ?? ""}
        </li>
      ))}
    </ul>
  );
}

export function ConversationDetailRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token, role } = useStaffSession();
  const canUseTools = role === "senior" || role === "engineer";
  const nav = useNavigate();
  const [events, pushEvent] = useStaffStream(token, convId);
  const [taken, setTaken] = useState(false);
  const [notice, setNotice] = useState("");
  const { draftMode, aiDraft, toggleDraftMode, approve, reject } = useAiDraft(token, convId, events);

  useEffect(() => {
    if (!token) nav("/staff/login");
  }, [token, nav]);

  async function onToggleDraftMode() {
    const msg = await toggleDraftMode();
    if (msg) setNotice(msg);
  }

  async function onTake() {
    if (!token) return;
    const ok = await takeConversation(token, convId);
    setTaken(ok);
    setNotice(ok ? "已接管" : "该会话已被其他客服接管");
  }

  async function onRelease() {
    if (!token) return;
    await releaseConversation(token, convId);
    setTaken(false);
    setNotice("已释放回 AI");
  }

  return (
    <PageContainer fullHeight>
      <PageHeader
        title={`会话 #${convId}`}
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={onToggleDraftMode}>
              {draftMode ? "关闭草稿模式" : "AI 草稿模式"}
            </Button>
            {taken ? (
              <Button size="sm" variant="ghost" onClick={onRelease}>
                释放回 AI
              </Button>
            ) : (
              <Button size="sm" onClick={onTake}>
                接管
              </Button>
            )}
          </>
        }
      />
      {notice && (
        <Alert variant="info" className="mb-2">
          {notice}
        </Alert>
      )}
      <AiDraftPanel draft={aiDraft} onApprove={approve} onReject={reject} />
      {canUseTools && token && (
        <div className="mb-3">
          <AiToolsPanel token={token} convId={convId} />
        </div>
      )}
      <EventLog events={events} />
      {taken && token && (
        <TakeoverFooter token={token} convId={convId} onLocalEvent={pushEvent} onNotice={setNotice} />
      )}
    </PageContainer>
  );
}
```

> `notice` 既有取值含 "已接管"（接管成功）也含错误类文案；统一用 `variant="info"` 中性提示，保持与原 `text-ink-secondary` 观感一致，且不影响测试（测试只断言文本存在）。

- [ ] **Step 3: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/staff.test.tsx tests/multiStaff.test.tsx`
Expected: 均 PASS。

- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/ConversationDetailRoute.tsx
git commit -m "refactor(web): 会话详情统一为 PageContainer/PageHeader/Alert"
```

---

### Task 7: 重构 SpectateRoute

**Files:**
- Modify: `web/src/routes/staff/SpectateRoute.tsx`
- Test: `web/tests/spectate.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/spectate.test.tsx`
Expected: PASS（断言 "AI：正在为您查询""用户：我卡被锁了"）。

- [ ] **Step 2: 重写文件**

`web/src/routes/staff/SpectateRoute.tsx`（`label()` 函数与流逻辑不变）:

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { streamSpectateEvents, type StaffStreamEvent } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

function label(ev: StaffStreamEvent): string {
  if (ev.type === "assistant_text") return `AI：${ev.content ?? ""}`;
  if (ev.type === "user_message") return `用户：${ev.content ?? ""}`;
  if (ev.type === "tool_call") return `调用工具：${ev.content ?? ""}`;
  if (ev.type === "mode_change") return `模式切换 → ${ev.to ?? ""}`;
  return `[${ev.type}] ${ev.content ?? ""}`;
}

export function SpectateRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token, role } = useStaffSession();
  const nav = useNavigate();
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    let stopped = false;
    (async () => {
      try {
        for await (const ev of streamSpectateEvents(token, convId)) {
          if (stopped) break;
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        setErr("无法旁观（需 senior/engineer 权限）");
      }
    })();
    return () => {
      stopped = true;
    };
  }, [token, convId, nav]);

  return (
    <PageContainer fullHeight>
      <h2 className="mb-1 text-sh2 text-ink-primary">旁观会话 #{convId}</h2>
      <div className="mb-3 text-footnote text-ink-secondary">
        只读模式{role ? `（${role}）` : ""} · 不接管、不发消息
      </div>
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      <ul className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {events.map((ev, i) => (
          <li key={i} className="text-body2 text-ink-primary">
            {label(ev)}
          </li>
        ))}
        {events.length === 0 && !err && <EmptyState>等待会话活动…</EmptyState>}
      </ul>
    </PageContainer>
  );
}
```

- [ ] **Step 3: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/spectate.test.tsx`
Expected: 均 PASS。

- [ ] **Step 4: 提交**

```bash
git add web/src/routes/staff/SpectateRoute.tsx
git commit -m "refactor(web): 旁观页统一为 PageContainer/Alert/EmptyState"
```

---

### Task 8: 重构 PromptsRoute

**Files:**
- Modify: `web/src/routes/admin/PromptsRoute.tsx`
- Test: `web/tests/adminPrompts.test.tsx`（既有，保持绿）

- [ ] **Step 1: 确认基线测试通过**

Run: `pnpm exec vitest run tests/adminPrompts.test.tsx`
Expected: PASS（断言 "需要 admin 权限""v1.1.0""保存""已保存并热加载"）。

- [ ] **Step 2: 重写文件**

`web/src/routes/admin/PromptsRoute.tsx`（保留 aria-label `${v} 灰度比例`、合计校验逻辑；用 form 宽度容器 + Card + Alert，数值输入用 Input）:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPromptVersions, setRollout } from "../../api/admin";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const nav = useNavigate();
  const [versions, setVersions] = useState<string[]>([]);
  const [rollout, setRolloutState] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      return;
    }
    getPromptVersions(token)
      .then((d) => {
        setVersions(d.versions);
        setRolloutState(d.rollout);
      })
      .catch(() => setErr("加载失败"));
  }, [token, role]);

  const total = Object.values(rollout).reduce((a, b) => a + (b || 0), 0);

  async function save() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      const next = await setRollout(token, rollout);
      setRolloutState(next);
      setNotice("已保存并热加载");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <PageContainer width="form">
      <PageHeader
        title="Prompt 灰度管理"
        actions={
          <Button variant="ghost" size="sm" onClick={() => nav("/staff/conversations")}>
            返回
          </Button>
        }
      />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {notice && (
        <Alert variant="success" className="mb-2">
          {notice}
        </Alert>
      )}
      <Card>
        <div className="flex flex-col gap-2 px-page py-block-sm">
          {versions.map((v) => (
            <div key={v} className="flex items-center gap-3">
              <span className="flex-1 text-body2 text-ink-primary">{v}</span>
              <Input
                type="number"
                min={0}
                max={100}
                aria-label={`${v} 灰度比例`}
                value={rollout[v] ?? 0}
                onChange={(e) =>
                  setRolloutState((prev) => ({ ...prev, [v]: Number(e.target.value) }))
                }
                className="w-20 px-2 py-1 text-body2"
              />
              <span className="text-body3 text-ink-secondary">%</span>
            </div>
          ))}
        </div>
      </Card>
      <div className="mt-2 text-footnote text-ink-secondary">
        合计 {total}%（≤100，余量回落 default）
      </div>
      <Button size="md" className="mt-3" onClick={save} disabled={total > 100}>
        保存
      </Button>
    </PageContainer>
  );
}
```

- [ ] **Step 3: 类型检查 + 测试**

Run: `pnpm typecheck && pnpm exec vitest run tests/adminPrompts.test.tsx`
Expected: 均 PASS。

- [ ] **Step 4: 提交**

```bash
git add web/src/routes/admin/PromptsRoute.tsx
git commit -m "refactor(web): Prompt 灰度页统一为 PageContainer/Card/Input/Alert"
```

---

### Task 9: C 端聊天一致性收尾 + 全量验证

**Files:**
- Modify: `web/src/components/MessageBubble.tsx`（`bg-yellow-50` → token）
- Modify: `web/src/components/TicketCard.tsx`（`bg-yellow-50/40` → token）
- Modify: `web/src/components/TicketStatusBanner.tsx`（`bg-fill-secondary` → token）
- Test: 全量 `web/tests/`（保持绿）

C 端聊天结构已成熟，本任务只做 token 一致性微调：消除默认色 `bg-yellow-50` 与未定义类 `bg-fill-secondary`，统一到设计 token。改动最小，不动结构与逻辑。

- [ ] **Step 1: 确认基线全量测试通过**

Run: `pnpm exec vitest run tests/components.test.tsx tests/ChatWindow.test.tsx tests/ticketStream.test.tsx`
Expected: PASS。

- [ ] **Step 2: MessageBubble — human_agent 气泡换 token**

在 `web/src/components/MessageBubble.tsx` 的 `human_agent` 分支，把：

```tsx
        <div className="flex-1 max-w-[80%] rounded-lg bg-yellow-50 border border-status-warning/30 px-page py-block-sm">
```

改为：

```tsx
        <div className="flex-1 max-w-[80%] rounded-lg bg-status-warning/10 border border-status-warning/30 px-page py-block-sm">
```

- [ ] **Step 3: TicketCard — 卡片底色换 token**

在 `web/src/components/TicketCard.tsx`，把：

```tsx
    <Card className="bg-yellow-50/40">
```

改为：

```tsx
    <Card className="bg-status-warning/5">
```

- [ ] **Step 4: TicketStatusBanner — 修复未定义类**

在 `web/src/components/TicketStatusBanner.tsx`，把：

```tsx
    <div className="px-page py-2 bg-fill-secondary text-body3 text-ink-secondary border-b border-line">
```

改为：

```tsx
    <div className="px-page py-2 bg-surface-subtle text-body3 text-ink-secondary border-b border-line">
```

- [ ] **Step 5: 全量验证**

Run: `pnpm typecheck`
Expected: 无错误。

Run: `pnpm exec vitest run`
Expected: 全部测试 PASS（含 ui.test.tsx 及所有既有用例）。

Run: `pnpm lint`
Expected: 0 warnings/errors（`--max-warnings=0`）。

Run: `pnpm format`
Expected: 格式化无残留 diff（或仅本次改动文件被规整）。

Run: `pnpm build`
Expected: `tsc && vite build` 成功产出 `dist/`。

- [ ] **Step 6: 提交**

```bash
git add web/src/components/MessageBubble.tsx web/src/components/TicketCard.tsx web/src/components/TicketStatusBanner.tsx
git commit -m "refactor(web): C 端聊天 token 一致性（消除默认色与未定义类）"
```

---

## Self-Review

- **Spec coverage**：
  - §3.1 组件库 → Task 1（Input/Textarea/Field/Alert/Badge/PageContainer/PageHeader/FilterTabs/Table 原语/EmptyState 全覆盖；Spinner/Slider 按 YAGNI 删除——现有页面无加载 spinner，Prompts 用样式化数值 Input 替代 Slider，已在 spec §3.1 标注二选一）。
  - §3.2 逐页：登录→Task 2；会话列表→Task 3；KPI→Task 4；详情→Task 6；Spectate→Task 7；Prompts→Task 8；C 端聊天微调→Task 9。客服侧面板（详情依赖）→Task 5。
  - §3.3 工程约束：每任务含 typecheck + 定向测试，Task 9 含全量 test/lint/format/build。token 未新增。
  - §5 非目标：未引入导航重构、未改后端/路由/依赖。
- **Placeholder scan**：无 TBD/TODO；每个改文件均给出完整代码或精确字符串替换。
- **Type consistency**：新组件命名在各任务一致（`PageContainer`/`PageHeader` 来自 `ui/page`；`Table/THead/TBody/Tr/Th/Td` 来自 `ui/table`；`Input/Textarea` 来自 `ui/input`）。各 import 路径与文件名对应。
- **测试保留项**：所有既有断言文案/placeholder/aria-label 在重构代码中逐字保留（见各任务）。
