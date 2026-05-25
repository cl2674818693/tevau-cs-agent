# 亮色+靛蓝底座 + C 端聊天重做 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/` 全局设计 token 从「深色青」换成「亮色+靛蓝」底座，并将 C 端聊天界面按新底座完整重做。

**Architecture:** 第一步 revalue `tailwind.config.ts` 现有 token 名（保留名、改值）一次性把全站重新着色为亮色，并清理 `globals.css` 的深色科技感残留（网格/辉光/呼吸/多字体）。随后逐个重写聊天组件（仅展示层，props/hooks/事件不动），用语义 token + 阴影替代写死色与辉光，圆角与字体统一。员工台/后台会随底座自动变亮，其完整打磨是后续独立计划。

**Tech Stack:** React 18 + Vite + TypeScript + Tailwind + radix + lucide + vitest/testing-library；pnpm。

**对应 spec：** `docs/superpowers/specs/2026-05-25-web-light-indigo-redesign-design.md`

---

## 文件结构

**底座（影响全站）**
- Modify: `web/tailwind.config.ts` — 颜色/字体/圆角/阴影/背景 token revalue
- Modify: `web/src/styles/globals.css` — 字体 import、body、focus、删除深色效果类、markdown 改亮色

**C 端聊天（仅展示层重写）**
- Modify: `web/src/components/ChatWindow.tsx` — 亮色根容器 + 空状态 + 按需转人工条
- Modify: `web/src/components/ChatExtras.tsx` — ChatHeader/LoadingView/ErrorView/StatusBanners 亮色 + 新增 EmptyState，删除 Suggestions
- Modify: `web/src/components/MessageBubble.tsx` — 四种 role 亮色气泡
- Modify: `web/src/components/ToolCallChip.tsx` — 亮色 chip
- Modify: `web/src/components/InputBox.tsx` — 亮色输入框 + 靛蓝焦点环
- Modify: `web/src/components/TicketCard.tsx` — 亮色工单卡
- Modify: `web/src/components/TicketStatusBanner.tsx` — 亮色状态条（核对后）
- Modify: `web/src/components/HandoffButton.tsx` — 改为内联「转人工」行动条 HandoffPrompt
- Modify: `web/tests/components.test.tsx` — 同步 HandoffButton 文案锚点

**验证**
- `web/tests/*.test.tsx`（全绿）、`pnpm typecheck` / `pnpm test:ci` / `pnpm build` / `pnpm lint` / `pnpm format`

---

## Task 1: 换底座 token（tailwind.config.ts）

**Files:**
- Modify: `web/tailwind.config.ts`

- [ ] **Step 1: 替换 `theme.extend.colors` 整块**

把现有 `colors: { ... }` 整块替换为：

```ts
      colors: {
        brand: {
          DEFAULT: "#4F46E5",
          dark: "#4338CA",
          tab: "#6366F1",
          press: "#3730A3",
          disabled: "#E9ECF1",
        },
        ink: {
          primary: "#0F172A",
          secondary: "#64748B",
          placeholder: "#94A3B8",
          subtle: "#64748B",
          footnote: "#94A3B8",
          onbrand: "#FFFFFF",
        },
        surface: {
          page: "#F7F8FA",
          card: "#FFFFFF",
          subtle: "#F1F3F5",
          container: "#FFFFFF",
          disabled: "#E9ECF1",
          hover: "#F1F3F5",
        },
        line: "#E2E8F0",
        status: {
          error: "#DC2626",
          success: "#16A34A",
          warning: "#D97706",
        },
        soft: {
          brand: "#EEF0FE",
          success: "#DCFCE7",
          warning: "#FEF3C7",
          error: "#FEE2E2",
        },
        background: "#F7F8FA",
        foreground: "#0F172A",
        primary: { DEFAULT: "#4F46E5", foreground: "#FFFFFF" },
        secondary: { DEFAULT: "#EEF0FE", foreground: "#3730A3" },
        muted: { DEFAULT: "#F1F3F5", foreground: "#64748B" },
        accent: { DEFAULT: "#EEF0FE", foreground: "#3730A3" },
        destructive: { DEFAULT: "#DC2626", foreground: "#FFFFFF" },
        border: "#E2E8F0",
        input: "#E2E8F0",
        ring: "#4F46E5",
        card: { DEFAULT: "#FFFFFF", foreground: "#0F172A" },
        chat: {
          primary: "#4F46E5",
          "on-primary": "#FFFFFF",
          surface: "#F7F8FA",
          "surface-variant": "#FFFFFF",
          "on-surface": "#0F172A",
          "on-surface-variant": "#64748B",
          accent: "#D97706",
        },
      },
```

- [ ] **Step 2: 字体统一为一套（Inter + PingFang）**

把 `fontFamily` 整块替换为（chat-* 全部指向 Inter 栈，避免遗留引用破样式）：

```ts
      fontFamily: {
        sans: ['"Inter"', "-apple-system", '"PingFang SC"', '"Microsoft YaHei"', "system-ui", "sans-serif"],
        "chat-headline": ['"Inter"', "-apple-system", '"PingFang SC"', "system-ui", "sans-serif"],
        "chat-body": ['"Inter"', "-apple-system", '"PingFang SC"', "system-ui", "sans-serif"],
        "chat-label": ['"Inter"', "-apple-system", '"PingFang SC"', "system-ui", "sans-serif"],
      },
```

- [ ] **Step 3: 圆角 / 阴影 / 背景 token**

把 `borderRadius`、`boxShadow`、`backgroundImage` 三块分别替换为：

```ts
      borderRadius: {
        sm: "8px",
        DEFAULT: "10px",
        md: "12px",
        lg: "14px",
        xl: "16px",
      },
```
```ts
      boxShadow: {
        focus: "0 0 0 3px rgba(79, 70, 229, 0.18)",
        sm: "0 1px 2px rgba(15, 23, 42, 0.05)",
        md: "0 4px 12px rgba(15, 23, 42, 0.08)",
        lg: "0 8px 24px rgba(15, 23, 42, 0.10)",
      },
```
```ts
      backgroundImage: {
        "page-gradient": "linear-gradient(180deg, #F7F8FA 0%, #F7F8FA 100%)",
      },
```

`fontSize`、`spacing`、`transitionDuration`、`transitionTimingFunction` 保持不变。

- [ ] **Step 4: 验证 typecheck**

Run: `cd web && pnpm typecheck`
Expected: PASS（仅改 token 值，无类型变化）

- [ ] **Step 5: Commit**

```bash
git add web/tailwind.config.ts
git commit -m "feat(ui): 换设计底座 token 为亮色+靛蓝"
```

---

## Task 2: 清理 globals.css（亮色化 + 删深色效果）

**Files:**
- Modify: `web/src/styles/globals.css`

- [ ] **Step 1: 用以下完整内容替换整个文件**

```css
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap");

@tailwind base;
@tailwind components;
@tailwind utilities;

html,
body,
#root {
  height: 100%;
}

body {
  font-family:
    "Inter",
    -apple-system,
    "PingFang SC",
    "Microsoft YaHei",
    system-ui,
    sans-serif;
  background: #f7f8fa;
  color: #0f172a;
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}

.safe-top {
  padding-top: env(safe-area-inset-top);
}
.safe-bottom {
  padding-bottom: env(safe-area-inset-bottom);
}

/* 亮色聚焦环（替代旧 cyan 辉光） */
.focus-glow:focus-within {
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.18);
  border-color: #4f46e5 !important;
  transition: all 200ms;
}

/* 隐藏滚动条但保留滚动能力 */
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

/* ===== 亮色 markdown（assistant 气泡内） ===== */
.markdown-body-dark {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}
.markdown-body-dark p {
  margin: 0 0 8px 0;
}
.markdown-body-dark p:last-child {
  margin-bottom: 0;
}
.markdown-body-dark strong {
  font-weight: 700;
  color: #0f172a;
}
.markdown-body-dark ul,
.markdown-body-dark ol {
  padding-left: 20px;
  margin: 8px 0;
}
.markdown-body-dark li {
  margin: 2px 0;
}
.markdown-body-dark code {
  background: #eef0fe;
  color: #4338ca;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, "SF Mono", monospace;
  font-size: 13px;
}
.markdown-body-dark pre {
  background: #0f172a;
  color: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: 13px;
}
.markdown-body-dark pre code {
  background: transparent;
  color: inherit;
  padding: 0;
}
.markdown-body-dark blockquote {
  border-left: 3px solid #4f46e5;
  padding-left: 12px;
  color: #64748b;
  margin: 8px 0;
}
.markdown-body-dark a {
  color: #4f46e5;
  text-decoration: underline;
}
.markdown-body-dark table {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  width: max-content;
  min-width: 100%;
}
.markdown-body-dark th,
.markdown-body-dark td {
  border: 1px solid #e2e8f0;
  padding: 6px 10px;
  text-align: left;
  white-space: nowrap;
  vertical-align: top;
}
.markdown-body-dark th {
  background: #f1f5f9;
  color: #0f172a;
  font-weight: 700;
}
.markdown-body-dark tr:nth-child(even) td {
  background: #f8fafc;
}
```

说明：删除了 `.glass / .cyan-glow-border / .amber-glow-border / .grid-bg / .animate-breathe / @keyframes breathe / .markdown-body(浅) ` 以及旧字体 import。已确认这些类仅被聊天组件引用，下面任务会同步去掉这些 className。保留 `.markdown-body-dark` 类名（值改亮色），MessageBubble 继续用它，减少改动面。

- [ ] **Step 2: 验证构建可解析**

Run: `cd web && pnpm typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/styles/globals.css
git commit -m "feat(ui): globals.css 亮色化，移除深色科技感效果类"
```

---

## Task 3: MessageBubble 亮色重写

**Files:**
- Modify: `web/src/components/MessageBubble.tsx`
- Test: `web/tests/components.test.tsx`（已有，断言不变）

- [ ] **Step 1: 先跑现有测试确认基线绿**

Run: `cd web && pnpm vitest run tests/components.test.tsx`
Expected: PASS（4 个 MessageBubble 用例）

- [ ] **Step 2: 用以下完整内容替换文件**

```tsx
import { BadgeCheck } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Message } from "../types";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ToolCallChip } from "./ToolCallChip";

export function MessageBubble({ m, userType = "b" }: { m: Message; userType?: "c" | "b" }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg rounded-tr-sm bg-brand text-ink-onbrand px-4 py-2.5 text-body1 font-medium whitespace-pre-wrap">
          {m.content}
        </div>
      </div>
    );
  }
  if (m.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="text-footnote text-ink-secondary py-1 px-3 rounded-full bg-surface-subtle">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "human_agent") {
    return (
      <div className="flex gap-3 items-start">
        <Avatar className="rounded-sm h-7 w-7">
          <AvatarFallback className="rounded-sm bg-soft-warning text-status-warning font-bold">
            客
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[85%]">
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-footnote font-bold text-status-warning">
              客服 {m.display_name ?? ""}
            </span>
            <BadgeCheck className="h-3 w-3 text-status-warning" />
            <span className="text-footnote text-ink-secondary">· 已认证</span>
          </div>
          <div className="bg-soft-warning border border-status-warning/30 rounded-lg rounded-tl-sm px-4 py-2.5 text-body1 text-ink whitespace-pre-wrap">
            {m.content}
          </div>
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-3 items-start">
      <Avatar className="rounded-sm h-7 w-7">
        <AvatarFallback className="rounded-sm bg-brand text-ink-onbrand font-bold">
          T
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 max-w-[85%] bg-surface-card border border-line shadow-sm rounded-lg rounded-tl-sm px-4 py-3 space-y-2">
        {(m.tool_calls ?? []).map((tc, i) => (
          <ToolCallChip key={i} tc={tc} userType={userType} />
        ))}
        <div className="markdown-body-dark">
          {m.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node: _node, ...props }) => (
                  <div className="overflow-x-auto scrollbar-hide -mx-1 px-1">
                    <table {...props} />
                  </div>
                ),
              }}
            >
              {m.content}
            </ReactMarkdown>
          ) : (
            <span className="text-ink-secondary text-body2">思考中…</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 跑测试**

Run: `cd web && pnpm vitest run tests/components.test.tsx`
Expected: PASS（文案锚点「你好啊」「欢迎」「search_code」「结论」「思考中…」未变）

- [ ] **Step 4: Commit**

```bash
git add web/src/components/MessageBubble.tsx
git commit -m "feat(chat): MessageBubble 亮色重写"
```

---

## Task 4: ToolCallChip 亮色

**Files:**
- Modify: `web/src/components/ToolCallChip.tsx`
- Test: `web/tests/components.test.tsx` + `web/tests/identityAndChips.test.tsx`（断言不变）

- [ ] **Step 1: 替换 `CToolChip` 与 B 端容器的 className**

`CToolChip` 的外层 div className 改为：

```tsx
    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-sm bg-soft-brand border border-brand/20 text-brand text-body3">
```

B 端 `ToolCallChip` 返回的外层 `<div className="rounded bg-chat-surface-variant/50">` 改为：

```tsx
    <div className="rounded-sm bg-surface-subtle">
```

按钮 className 中 `text-chat-on-surface-variant hover:bg-chat-surface-variant` 改为 `text-ink-secondary hover:bg-surface-hover`；展开 `<pre>` 的 `text-chat-on-surface-variant` 改为 `text-ink-secondary`。`color` 变量里的 `text-chat-on-surface-variant` 改为 `text-ink-secondary`，`text-status-success`/`text-status-error` 保留。

- [ ] **Step 2: 跑测试**

Run: `cd web && pnpm vitest run tests/components.test.tsx tests/identityAndChips.test.tsx`
Expected: PASS（`query_user` 可展开、`正在查询卡片状态…` 文案不变）

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ToolCallChip.tsx
git commit -m "feat(chat): ToolCallChip 亮色"
```

---

## Task 5: InputBox 亮色 + 靛蓝焦点环

**Files:**
- Modify: `web/src/components/InputBox.tsx`
- Test: `web/tests/ChatWindow.test.tsx`（placeholder/aria-label 不变）

- [ ] **Step 1: 替换 return 的两个容器与按钮 className**

外层容器：
```tsx
    <div className="border-t border-line bg-surface-card px-page py-block-sm safe-bottom">
```
输入行容器：
```tsx
      <div className="flex items-end gap-2 rounded-md bg-surface-page border border-line px-3 py-2 transition-all focus-within:border-brand focus-within:shadow-focus">
```
textarea className：
```tsx
          className="flex-1 resize-none bg-transparent text-body1 leading-6 text-ink placeholder:text-ink-placeholder outline-none max-h-32 overflow-y-auto scrollbar-hide py-0.5"
```
发送按钮（去掉辉光 style，改 box-shadow 无）：
```tsx
        <button
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="grid h-10 w-10 place-items-center rounded bg-brand text-ink-onbrand transition-all hover:bg-brand-dark active:scale-90 disabled:opacity-40 disabled:bg-surface-disabled disabled:text-ink-placeholder"
        >
          <Send className="h-4 w-4" />
        </button>
```
删除该 button 上的 `style={{ boxShadow: ... }}`。

- [ ] **Step 2: 跑测试**

Run: `cd web && pnpm vitest run tests/ChatWindow.test.tsx`
Expected: PASS（placeholder「描述你的问题…」、`aria-label="发送"` 不变）

- [ ] **Step 3: Commit**

```bash
git add web/src/components/InputBox.tsx
git commit -m "feat(chat): InputBox 亮色 + 靛蓝焦点环"
```

---

## Task 6: TicketCard 亮色

**Files:**
- Modify: `web/src/components/TicketCard.tsx`
- Test: `web/tests/components.test.tsx`（按钮/状态文案不变）

- [ ] **Step 1: 用以下完整内容替换文件**

```tsx
import { CheckCircle2, Ticket, XCircle } from "lucide-react";

function statusLabel(s: string) {
  return (
    {
      pending: "等待受理",
      assigned: "已分派",
      in_progress: "处理中",
      resolved: "已处理",
      closed: "已关闭",
    }[s] ?? s
  );
}

export function TicketCard({
  externalId,
  summary,
  status = "pending",
  onConfirm,
  onReject,
}: {
  externalId: string;
  summary: string;
  status?: "pending" | "assigned" | "in_progress" | "resolved" | "closed";
  onConfirm?: () => void;
  onReject?: () => void;
}) {
  return (
    <div className="bg-surface-card border border-line shadow-sm rounded-md overflow-hidden">
      <div className="flex items-center gap-2 px-page py-block-sm border-b border-line text-body3">
        <Ticket className="h-3.5 w-3.5 text-brand" />
        <span className="font-mono text-ink-secondary">{externalId}</span>
        <span className="ml-auto px-2 py-0.5 rounded-full bg-soft-warning text-status-warning text-footnote font-bold">
          {statusLabel(status)}
        </span>
      </div>
      <div className="px-page py-block-sm space-y-3">
        <div className="text-body2 text-ink">{summary}</div>
        {status === "resolved" && (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={onConfirm}
              className="flex items-center justify-center gap-1 bg-brand text-ink-onbrand text-body3 font-bold py-2.5 rounded active:scale-95 transition-all hover:bg-brand-dark"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </button>
            <button
              onClick={onReject}
              className="flex items-center justify-center gap-1 border border-line text-ink-secondary text-body3 font-bold py-2.5 rounded active:scale-95 transition-all hover:bg-surface-hover"
            >
              <XCircle className="h-3.5 w-3.5" /> 未解决
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 跑测试**

Run: `cd web && pnpm vitest run tests/components.test.tsx`
Expected: PASS（「已解决」「未解决」「等待受理」不变）

- [ ] **Step 3: Commit**

```bash
git add web/src/components/TicketCard.tsx
git commit -m "feat(chat): TicketCard 亮色"
```

---

## Task 7: TicketStatusBanner 亮色

**Files:**
- Modify: `web/src/components/TicketStatusBanner.tsx`

- [ ] **Step 1: 读文件，确认其 className 中的深色/辉光/玻璃用法**

Run: `cat web/src/components/TicketStatusBanner.tsx`
按以下规则替换 className（不改逻辑/文案）：`glass`→`bg-surface-card`；`text-chat-*`→对应 `text-ink`/`text-ink-secondary`；`border-chat-primary/*`/`border-white/*`→`border-line`；任何 `bg-chat-accent/10 text-chat-accent`→`bg-soft-warning text-status-warning`；`text-chat-primary`→`text-brand`。

- [ ] **Step 2: typecheck + 相关测试**

Run: `cd web && pnpm typecheck && pnpm vitest run tests/ticketStream.test.tsx`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/src/components/TicketStatusBanner.tsx
git commit -m "feat(chat): TicketStatusBanner 亮色"
```

---

## Task 8: HandoffButton → 内联「转人工」行动条

**Files:**
- Modify: `web/src/components/HandoffButton.tsx`
- Test: `web/tests/components.test.tsx`（更新文案锚点）

按需出现的转人工是**前端呈现规则**（无后端建议信号）：组件本身仍是受控展示件，由 ChatWindow 决定何时渲染（Task 9）。这里把它从「贴底大按钮」改为克制的内联行动条，保留 `onClick`/`disabled` 接口。

- [ ] **Step 1: 用以下完整内容替换文件**

```tsx
import { Headphones } from "lucide-react";

/**
 * 内联「转人工」行动条。由 ChatWindow 在 AI 模式、对话已开始时渲染于消息流末尾。
 * 点击调 useChat.requestHandoff → POST /request-human（spec §13.7）。
 */
export function HandoffPrompt({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <div className="flex justify-center px-page pb-1">
      <button
        onClick={onClick}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 py-1.5 px-3 rounded-full text-body3 text-ink-secondary transition-colors hover:text-brand hover:bg-soft-brand disabled:opacity-40"
      >
        <Headphones className="h-3.5 w-3.5" />
        转接人工客服
      </button>
    </div>
  );
}
```

- [ ] **Step 2: 更新 components.test.tsx 的 HandoffButton 用例**

把 `import { HandoffButton }` 改为 `import { HandoffPrompt }`，并把该 describe 块替换为：

```tsx
describe("HandoffPrompt", () => {
  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<HandoffPrompt onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByText("转接人工客服"));
    expect(onClick).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: 跑测试**

Run: `cd web && pnpm vitest run tests/components.test.tsx`
Expected: PASS（新锚点「转接人工客服」）

- [ ] **Step 4: Commit**

```bash
git add web/src/components/HandoffButton.tsx web/tests/components.test.tsx
git commit -m "feat(chat): 转人工改为内联克制行动条 HandoffPrompt"
```

---

## Task 9: ChatExtras 亮色 + 新增 EmptyState，删除 Suggestions

**Files:**
- Modify: `web/src/components/ChatExtras.tsx`

- [ ] **Step 1: 用以下完整内容替换文件**

```tsx
import { Wifi } from "lucide-react";

/** ChatWindow 的辅助呈现块（拆出以控制单组件复杂度）。 */

export function ChatHeader({
  mode,
  staffName,
  sending,
  onStop,
}: {
  mode: string;
  staffName?: string;
  sending: boolean;
  onStop: () => void;
}) {
  return (
    <header className="safe-top sticky top-0 z-10 flex items-center justify-between px-page py-3 bg-surface-card border-b border-line">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-md grid place-items-center bg-brand">
          <span className="text-ink-onbrand font-bold text-body0">T</span>
        </div>
        <div className="flex flex-col">
          <div className="text-sh3 font-bold text-ink-primary leading-none">Tevau 客服</div>
          <div className="flex items-center gap-1.5 mt-1">
            {mode !== "human_takeover" && (
              <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
            )}
            <span className="text-footnote text-ink-secondary">
              {mode === "human_takeover" ? `客服 ${staffName ?? ""} · 已认证` : "在线 · 智能助手"}
            </span>
          </div>
        </div>
      </div>
      {sending && (
        <button
          onClick={onStop}
          className="px-3 py-1.5 rounded text-body3 text-ink-secondary border border-line hover:bg-surface-hover transition-colors"
        >
          停止生成
        </button>
      )}
    </header>
  );
}

export function EmptyState({ greeting }: { greeting: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-8 gap-3">
      <div className="h-14 w-14 rounded-xl grid place-items-center bg-soft-brand">
        <span className="text-brand font-bold text-h2">T</span>
      </div>
      <div className="text-sh1 font-bold text-ink-primary">你好，我是 Tevau 助手</div>
      <p className="text-body2 text-ink-secondary leading-relaxed max-w-[320px]">{greeting}</p>
    </div>
  );
}

export function LoadingView() {
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center bg-surface-page text-ink-secondary">
      <div className="animate-pulse text-body2">正在连接 Tevau 客服…</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3 bg-surface-page">
      <div className="text-body2 text-status-error">连接失败，请检查网络后重试。</div>
      <button
        onClick={onRetry}
        className="rounded border border-line px-4 py-2 text-body2 text-brand hover:bg-soft-brand transition-colors"
      >
        重试
      </button>
    </div>
  );
}

export function StatusBanners({
  connection,
  limitPct,
}: {
  connection: "online" | "offline" | "reconnecting";
  limitPct: number;
}) {
  return (
    <>
      {connection !== "online" && (
        <div className="flex items-center justify-center gap-1.5 px-page py-1.5 bg-soft-warning border-b border-status-warning/30 text-body3 text-status-warning text-center">
          <Wifi className="h-3.5 w-3.5" />
          {connection === "offline" ? "网络已断开，正在等待重新连接…" : "正在重新连接…"}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-soft-warning text-body3 text-status-warning text-center">
          您今日用量已达 {limitPct}%，建议核心问题尽快咨询。
        </div>
      )}
    </>
  );
}
```

说明：删除了 `SUGGESTIONS` 常量与 `Suggestions` 组件（空状态不再放引导问题），并把呼吸点改为静态绿点。`EmptyState`/`HandoffPrompt` 暂为未被引用的导出（Task 10 接入），不影响 typecheck。ChatWindow 已不引用 `Suggestions`（本次重做前已移除），故删除安全。

- [ ] **Step 2: typecheck**

Run: `cd web && pnpm typecheck`
Expected: PASS（无残留对 `Suggestions` 的引用；新增导出未被用到不报错）

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ChatExtras.tsx
git commit -m "feat(chat): ChatExtras 亮色 + 居中 EmptyState，移除 Suggestions"
```

---

## Task 10: ChatWindow 亮色根容器 + 空状态 + 按需转人工

**Files:**
- Modify: `web/src/components/ChatWindow.tsx`
- Test: `web/tests/ChatWindow.test.tsx`

- [ ] **Step 1: 用以下完整内容替换文件**

```tsx
import { sendTicketUserEvent } from "../api/chat";
import { userType } from "../api/identity";
import { useChat } from "../hooks/useChat";
import { useTicketStream } from "../hooks/useTicketStream";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { ChatHeader, EmptyState, ErrorView, LoadingView, StatusBanners } from "./ChatExtras";
import { HandoffPrompt } from "./HandoffButton";
import { InputBox } from "./InputBox";
import { MessageList } from "./MessageList";
import { TicketCard } from "./TicketCard";
import { TicketStatusBanner } from "./TicketStatusBanner";

type TicketStatus = "pending" | "assigned" | "in_progress" | "resolved" | "closed";

function inputPlaceholder(rateLimited: boolean, mode: string): string {
  if (rateLimited) return "请求过于频繁，请稍后再试…";
  if (mode === "human_takeover") return "向客服留言…";
  return "描述你的问题…";
}

function TicketCardSlot({
  ticket,
  mode,
}: {
  ticket?: { external_id?: string; event: string; comment?: string };
  mode: string;
}) {
  if (!ticket?.external_id || ticket.event === "closed" || mode !== "ai") return null;
  const send = (resolved: boolean) =>
    void sendTicketUserEvent(
      ticket.external_id!,
      resolved ? "user_confirmed_resolved" : "user_rejected_resolved",
    );
  return (
    <div className="px-page pb-2">
      <TicketCard
        externalId={ticket.external_id}
        summary={ticket.comment ?? "您的工单进展"}
        status={ticket.event as TicketStatus}
        onConfirm={() => send(true)}
        onReject={() => send(false)}
      />
    </div>
  );
}

export function ChatWindow() {
  const chat = useChat();
  const { messages, sending, mode, send, init } = chat;
  const ticketEvents = useTicketStream(init?.conversation_id ?? null);
  const inset = useKeyboardInset();
  const isC = userType() === "c";

  if (chat.status === "loading") return <LoadingView />;
  if (chat.status === "error") return <ErrorView onRetry={chat.retryInit} />;

  const latestTicket = ticketEvents[ticketEvents.length - 1];
  const onlyGreeting = messages.length <= 1;
  const isAi = mode === "ai";
  const greeting = (messages[0]?.role === "system" && messages[0].content) || "";
  // 按需转人工：AI 模式、对话已开始、未在生成时，于消息流末尾给一个克制入口（无后端建议信号，纯前端呈现规则）。
  const showHandoff = isAi && !onlyGreeting && !sending;

  return (
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-surface-page text-ink"
      style={{ paddingBottom: inset }}
    >
      <ChatHeader mode={mode} staffName={chat.staffName} sending={sending} onStop={chat.stop} />

      <StatusBanners connection={chat.connection} limitPct={chat.limitPct} />
      <TicketStatusBanner events={ticketEvents} />

      {onlyGreeting && isAi ? (
        <EmptyState greeting={greeting} />
      ) : (
        <MessageList messages={messages} userType={isC ? "c" : "b"} />
      )}

      <TicketCardSlot ticket={latestTicket} mode={mode} />

      {showHandoff && <HandoffPrompt onClick={chat.requestHandoff} disabled={sending} />}

      <InputBox
        onSend={send}
        disabled={sending || chat.rateLimited}
        placeholder={inputPlaceholder(chat.rateLimited, mode)}
      />
    </div>
  );
}
```

说明：空状态（仅欢迎语且 AI 模式）渲染 `EmptyState`，否则渲染消息流；欢迎语从 `messages[0]`（init 写入的 system greeting）取。非 C 端（B 端）init 也是 system greeting，空状态同样适用。

- [ ] **Step 2: typecheck**

Run: `cd web && pnpm typecheck`
Expected: PASS

- [ ] **Step 3: 跑 ChatWindow 测试**

Run: `cd web && pnpm vitest run tests/ChatWindow.test.tsx`
Expected: PASS（发消息后 `messages.length>1`，渲染消息流并显示「已收到。」）

- [ ] **Step 4: Commit**

```bash
git add web/src/components/ChatWindow.tsx
git commit -m "feat(chat): 亮色根容器 + 居中空状态 + 按需转人工入口"
```

---

## Task 11: 全量验证

**Files:** 无（验证）

- [ ] **Step 1: 类型检查**

Run: `cd web && pnpm typecheck`
Expected: PASS

- [ ] **Step 2: 全量测试**

Run: `cd web && pnpm test:ci`
Expected: 全绿。若某非聊天页测试因 token 变色失败（不应该，测试不断言颜色 class），按其断言核对修复，不放宽断言、不删测试。

- [ ] **Step 3: lint + format**

Run: `cd web && pnpm format && pnpm lint`
Expected: 无 error

- [ ] **Step 4: 构建**

Run: `cd web && pnpm build`
Expected: 成功产出 dist

- [ ] **Step 5: 人工核对（用户）**

让用户冷启动 dev server / webview，对照 spec §4 检查：空状态居中只欢迎语、无网格/辉光/呼吸点、靛蓝按钮、AI/用户气泡亮色、对话中末尾出现克制「转接人工客服」入口、工单卡亮色。

- [ ] **Step 6: Commit（若 format 有改动）**

```bash
git add -A
git commit -m "chore(ui): format 收尾"
```

---

## 备注：后续独立计划（不在本计划内）

- **员工台**：登录/会话列表/会话详情/旁观/KPI + 共享 `ui/` 组件库（Button/Input/Card/Badge/Table/PageHeader/PageContainer/FilterTabs/Field/Alert/EmptyState/Spinner）。各自 spec→计划。
- **管理后台**：PromptsRoute。spec→计划。

本计划完成后，员工台/后台已随底座变为亮色但未做组件化打磨，属预期中间态。
