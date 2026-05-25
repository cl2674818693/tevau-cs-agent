# 其他端深色科技感统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把其他端（登录/工作台/后台）统一到深色科技感，通过重定义全局 token + 少量 ui 组件文字修正实现，不改业务逻辑。

**Architecture:** 改 `tailwind.config.ts` 全局 token 值（保留 token 名）→ 全站页面与 ui 组件自动深色；改 `globals.css` body/focus；改 4 个 ui 组件因 brand→cyan 的文字对比。C 端用 `chat-*` 独立 token 不受影响。

**Tech Stack:** React 18 + Vite + TS + Tailwind。pnpm。

**测试策略：** 纯展示层，现有测试是回归网。每任务后 `pnpm typecheck` + `pnpm test:ci`。命令工作目录 `web/`。

**测试锚点（不得改动）：** ui.test 的 Badge 含 `status-warning` class、FilterTabs active 含 `bg-brand` class、Input placeholder 透传、FilterTabs onChange；其他端测试断言文案/role。

---

### Task 1: 全局 token + globals 深色化

**Files:**
- Modify: `web/tailwind.config.ts`（colors / boxShadow.focus / backgroundImage.page-gradient）
- Modify: `web/src/styles/globals.css`（body / focus-glow）

- [ ] **Step 1: 替换 `tailwind.config.ts` 的 colors 块（从 `brand: {` 到 `card: {...}` 行，保留其后的 `chat:` 块不动）**

将现有浅色 token 值整体替换为：

```ts
      colors: {
        brand: {
          DEFAULT: "#22D3EE",
          dark: "#0E7490",
          tab: "#67E8F9",
          press: "#0891B2",
          disabled: "#1A232E",
        },
        ink: {
          primary: "#F8FAFC",
          secondary: "#94A3B8",
          placeholder: "#64748B",
          subtle: "#94A3B8",
          footnote: "#64748B",
          onbrand: "#06141B",
        },
        surface: {
          page: "#0B0F14",
          card: "#121A23",
          subtle: "#161F2A",
          container: "#1A232E",
          disabled: "#161F2A",
          hover: "#1F2A37",
        },
        line: "#243140",
        status: {
          error: "#F87171",
          success: "#4ADE80",
          warning: "#F59E0B",
        },
        background: "#0B0F14",
        foreground: "#F8FAFC",
        primary: { DEFAULT: "#22D3EE", foreground: "#06141B" },
        secondary: { DEFAULT: "#0E7490", foreground: "#F8FAFC" },
        muted: { DEFAULT: "#1A232E", foreground: "#94A3B8" },
        accent: { DEFAULT: "#67E8F9", foreground: "#06141B" },
        destructive: { DEFAULT: "#F87171", foreground: "#06141B" },
        border: "#243140",
        input: "#243140",
        ring: "#22D3EE",
        card: { DEFAULT: "#121A23", foreground: "#F8FAFC" },
```

（紧随其后的 `chat: { ... },` 与 `},` 保持不变。）

- [ ] **Step 2: 替换 `tailwind.config.ts` 的 boxShadow.focus 与 backgroundImage.page-gradient**

```ts
      boxShadow: {
        focus: "0 0 8px 0 rgba(34, 211, 238, 0.25)",
      },
      backgroundImage: {
        "page-gradient": "linear-gradient(180deg, #0B0F14 0%, #0E1620 100%)",
      },
```

- [ ] **Step 3: 改 `globals.css` 的 body 与 focus-glow**

把 body 的 `background-image` 与 `color`：

```css
  background-image: linear-gradient(180deg, #f6f6f6 0%, #fefefe 100%);
  background-attachment: fixed;
  color: #121212;
```

替换为：

```css
  background-image: linear-gradient(180deg, #0b0f14 0%, #0e1620 100%);
  background-attachment: fixed;
  color: #f8fafc;
```

把 `.focus-glow:focus-within`：

```css
.focus-glow:focus-within {
  box-shadow: 0 0 8px 0 rgba(200, 248, 51, 0.15);
  border-color: #c8f833 !important;
  border-width: 1.2px !important;
  transition: all 250ms;
}
```

替换为：

```css
.focus-glow:focus-within {
  box-shadow: 0 0 8px 0 rgba(34, 211, 238, 0.25);
  border-color: #22d3ee !important;
  border-width: 1.2px !important;
  transition: all 250ms;
}
```

- [ ] **Step 4: 验证**

Run: `pnpm typecheck && pnpm build`
Expected: PASS（config 语法正确，CSS 编译）。

- [ ] **Step 5: Commit**

```bash
git add web/tailwind.config.ts web/src/styles/globals.css
git commit -m "feat(ui): 全局 token 深色科技感化"
```

---

### Task 2: ui 组件文字色修正（cyan 底配深字）

**Files:**
- Modify: `web/src/components/ui/button.tsx:14-15`
- Modify: `web/src/components/ui/filter-tabs.tsx:24`
- Modify: `web/src/components/ui/badge.tsx:8`
- Modify: `web/src/components/ui/avatar.tsx`

- [ ] **Step 1: button.tsx primary 文字改 onbrand**

把：

```tsx
        primary:
          "bg-brand text-ink-primary hover:bg-brand-tab active:bg-brand-press active:text-white",
```

替换为：

```tsx
        primary:
          "bg-brand text-ink-onbrand hover:bg-brand-tab active:bg-brand-press",
```

- [ ] **Step 2: filter-tabs.tsx active 文字改 onbrand**

把：

```tsx
              ? "bg-brand text-ink-primary"
```

替换为：

```tsx
              ? "bg-brand text-ink-onbrand"
```

- [ ] **Step 3: badge.tsx takeover 文字改 onbrand**

把：

```tsx
  takeover: "bg-brand-tab text-ink-primary",
```

替换为：

```tsx
  takeover: "bg-brand-tab text-ink-onbrand",
```

- [ ] **Step 4: avatar.tsx fallback 文字改 onbrand**

先 Read `web/src/components/ui/avatar.tsx` 确认 fallback 用了 `bg-brand text-ink-primary`，把其中的 `text-ink-primary` 改为 `text-ink-onbrand`（仅 fallback 处；若无 `text-ink-primary` 则跳过本步）。

- [ ] **Step 5: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（ui.test 的 `bg-brand`、`status-warning` class 仍命中；其他端测试全绿）。

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ui/button.tsx web/src/components/ui/filter-tabs.tsx web/src/components/ui/badge.tsx web/src/components/ui/avatar.tsx
git commit -m "feat(ui): cyan 底文字改深色（onbrand）"
```

---

### Task 3: 全量验证与人工核对

**Files:** 无新增改动。

- [ ] **Step 1: 全量验证**

Run: `pnpm typecheck && pnpm test:ci && pnpm build`
Expected: 全 PASS。

- [ ] **Step 2: 仅对改动文件格式化与 lint**

Run（在 web/）：
`pnpm exec prettier --write tailwind.config.ts src/styles/globals.css src/components/ui/button.tsx src/components/ui/filter-tabs.tsx src/components/ui/badge.tsx src/components/ui/avatar.tsx`
然后：
`pnpm exec eslint src/components/ui/button.tsx src/components/ui/filter-tabs.tsx src/components/ui/badge.tsx src/components/ui/avatar.tsx --max-warnings=0`
Expected: prettier 无残留、eslint 无 warning。

- [ ] **Step 3: 人工核对（pnpm dev）**

打开登录页（Bu/Staff）、会话列表、会话详情、Spectate、KPI、Prompts，确认：深底+浅字、cyan 主按钮（深字）、cyan 激活态/聚焦、卡片/表格/Badge 深色可读、Alert 状态色清晰。C 端聊天仍正常。
Expected: 全站深色统一、可读性良好。

- [ ] **Step 4: Commit（若 prettier 有改动）**

```bash
git add web/tailwind.config.ts web/src/styles/globals.css web/src/components/ui/
git commit -m "chore(ui): 格式化收尾"
```

---

## Self-Review 记录

- **Spec 覆盖：** §3 token → Task1 Step1-2；§4 globals → Task1 Step3；§5 组件点缀 → Task2；§7 测试锚点 → Task2 验证；§8 工程 → Task3。无遗漏。
- **占位符扫描：** 无 TBD/TODO。avatar 步骤含条件（若无则跳过），执行时 Read 确认。
- **类型一致：** 新增 `ink.onbrand` 在 Task1 定义，Task2 引用，命名一致；保留全部 token 名，class 名不变。
