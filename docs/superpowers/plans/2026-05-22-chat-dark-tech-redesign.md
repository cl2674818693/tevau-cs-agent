# C 端聊天深色科技感重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 C 端聊天界面（`ChatWindow` + chat 组件）的视觉重做为深色科技感（深蓝灰底 + cyan #22D3EE + 玻璃拟态 + 微光网格），不改任何业务逻辑、数据流、文案锚点。

**Architecture:** 新增 `chat-*` Tailwind 色板 + 作用域自定义类（`.glass/.cyan-glow-border/.grid-bg` 等），不碰现有全局浅色 token；逐个聊天组件只替换 className/呈现结构，props/hooks/事件/条件分支保持不变。

**Tech Stack:** React 18 + Vite + TypeScript + Tailwind + lucide-react + react-markdown。包管理器 pnpm。

**测试策略：** 纯展示层重构，无新增颜色断言测试。现有 `web/tests/*` 覆盖文案/aria/交互，作为回归网。每个任务改完跑 `pnpm typecheck` + `pnpm test:ci` 保持全绿。所有命令工作目录为 `web/`。

**测试锚点（任何任务都不得改动这些文案/属性）：** placeholder `描述你的问题…`、`aria-label="发送"`、`没解决？转人工 →`、`已解决`/`未解决`、`等待受理`、`正在查询卡片状态…`、`query_card`/`query_user`、`search_code`、`结论`、`思考中…`、`Tevau AI 客服`。

---

### Task 1: 设计 token 底座

**Files:**
- Modify: `web/tailwind.config.ts`（colors 与 fontFamily）
- Modify: `web/src/styles/globals.css`（字体 import + 自定义类 + 深色 markdown）

- [ ] **Step 1: 在 `tailwind.config.ts` 的 `extend.colors` 末尾（`card: {...},` 之后）新增 `chat` 色板**

在 `colors` 对象内、`card: { DEFAULT: "#FFFFFF", foreground: "#121212" },` 这一行之后加入：

```ts
        chat: {
          primary: "#22D3EE",
          "on-primary": "#0B0F14",
          surface: "#0B0F14",
          "surface-variant": "#1A232E",
          "on-surface": "#F8FAFC",
          "on-surface-variant": "#94A3B8",
          accent: "#F59E0B",
        },
```

- [ ] **Step 2: 在 `tailwind.config.ts` 的 `extend.fontFamily` 中新增聊天字体**

把现有 `fontFamily` 块替换为：

```ts
      fontFamily: {
        sans: ['"Source Sans 3"', "-apple-system", "PingFang SC", "sans-serif"],
        "chat-headline": ['"Space Grotesk"', "sans-serif"],
        "chat-body": ['"Inter"', "sans-serif"],
        "chat-label": ['"Public Sans"', "sans-serif"],
      },
```

- [ ] **Step 3: 在 `globals.css` 合并字体 `@import`（替换第 5 行现有 import）**

把现有：

```css
@import url("https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700;800&display=swap");
```

替换为：

```css
@import url("https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&family=Public+Sans:wght@400;700&display=swap");
```

- [ ] **Step 4: 在 `globals.css` 末尾追加自定义类与深色 markdown**

```css
/* ===== C 端聊天深色科技感（作用域类，来自 Stitch 设计） ===== */
.glass {
  background: rgba(11, 15, 20, 0.7);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}
.cyan-glow-border {
  border: 1px solid rgba(34, 211, 238, 0.2);
  box-shadow: 0 0 15px rgba(34, 211, 238, 0.05);
}
.amber-glow-border {
  border: 1px solid rgba(245, 158, 11, 0.3);
}
.grid-bg {
  background-image: radial-gradient(circle at 2px 2px, rgba(34, 211, 238, 0.05) 1px, transparent 0);
  background-size: 24px 24px;
}
@keyframes breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.2);
    opacity: 1;
  }
}
.animate-breathe {
  animation: breathe 2s infinite ease-in-out;
}

.markdown-body-dark {
  font-size: 14px;
  line-height: 1.6;
}
.markdown-body-dark p {
  margin: 0 0 8px 0;
}
.markdown-body-dark p:last-child {
  margin-bottom: 0;
}
.markdown-body-dark strong {
  font-weight: 700;
  color: #f8fafc;
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
  background: rgba(34, 211, 238, 0.1);
  color: #22d3ee;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, "SF Mono", monospace;
  font-size: 13px;
}
.markdown-body-dark pre {
  background: #1a232e;
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
  border-left: 3px solid #22d3ee;
  padding-left: 12px;
  color: #94a3b8;
  margin: 8px 0;
}
.markdown-body-dark a {
  color: #22d3ee;
  text-decoration: underline;
}
```

- [ ] **Step 5: 验证编译**

Run: `pnpm typecheck && pnpm build`
Expected: 均 PASS（tsc 无错，vite build 产出 dist；新 token/类不影响现有页面）。

- [ ] **Step 6: Commit**

```bash
git add web/tailwind.config.ts web/src/styles/globals.css
git commit -m "feat(chat): 新增深色科技感设计 token 底座"
```

---

### Task 2: ChatWindow 根容器 + MessageList

**Files:**
- Modify: `web/src/components/ChatWindow.tsx:62-65`
- Modify: `web/src/components/MessageList.tsx:20`

- [ ] **Step 1: 改 ChatWindow 根容器 className**

把 `ChatWindow.tsx` 中根 `<div>`：

```tsx
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-page-gradient"
      style={{ paddingBottom: inset }}
    >
```

替换为：

```tsx
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-chat-surface grid-bg text-chat-on-surface font-chat-body"
      style={{ paddingBottom: inset }}
    >
```

- [ ] **Step 2: 改 MessageList 容器间距**

把 `MessageList.tsx` 的容器 `<div>`：

```tsx
    <div ref={ref} className="flex-1 overflow-y-auto px-page py-block-lg flex flex-col gap-3">
```

替换为：

```tsx
    <div ref={ref} className="flex-1 overflow-y-auto px-page py-block-lg flex flex-col gap-5">
```

- [ ] **Step 3: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（ChatWindow.test、ticketStream.test 等全绿）。

- [ ] **Step 4: Commit**

```bash
git add web/src/components/ChatWindow.tsx web/src/components/MessageList.tsx
git commit -m "feat(chat): ChatWindow 深色底 + 网格氛围"
```

---

### Task 3: ChatExtras（Header / StatusBanners / Suggestions / Loading / Error）

**Files:**
- Modify: `web/src/components/ChatExtras.tsx`（整文件）

- [ ] **Step 1: 用以下完整内容替换 `ChatExtras.tsx`**

保留导出的函数签名、`SUGGESTIONS` 文案、所有文案，仅改样式与新增 `Wifi` 图标。

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
    <header className="safe-top sticky top-0 z-10 flex items-center justify-between px-page py-3 glass border-b border-chat-primary/20">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg grid place-items-center bg-chat-primary/10 border border-chat-primary/30">
          <span className="text-chat-primary font-chat-headline text-body0 font-bold">T</span>
        </div>
        <div className="flex flex-col">
          <div className="font-chat-headline text-sh3 font-bold text-chat-primary leading-none">
            Tevau AI 客服
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            {mode !== "human_takeover" && (
              <span
                className="w-2 h-2 rounded-full bg-chat-primary animate-breathe"
                style={{ boxShadow: "0 0 8px rgba(34,211,238,0.8)" }}
              />
            )}
            <span className="text-footnote text-chat-on-surface-variant">
              {mode === "human_takeover"
                ? `客服 ${staffName ?? ""} · 已认证`
                : "由 AI 驱动 · 复杂问题转人工"}
            </span>
          </div>
        </div>
      </div>
      {sending && (
        <button
          onClick={onStop}
          className="px-3 py-1.5 rounded-lg border border-chat-primary/20 bg-chat-primary/5 text-body3 text-chat-primary hover:bg-chat-primary/10 transition-colors"
        >
          停止生成
        </button>
      )}
    </header>
  );
}

export function LoadingView() {
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center bg-chat-surface grid-bg text-chat-on-surface-variant">
      <div className="animate-pulse text-body2 font-chat-body">正在连接 Tevau AI 客服…</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3 bg-chat-surface grid-bg font-chat-body">
      <div className="text-body2 text-status-error">连接失败，请检查网络后重试。</div>
      <button
        onClick={onRetry}
        className="rounded-lg border border-chat-primary/30 px-4 py-2 text-body2 text-chat-primary hover:bg-chat-primary/10 transition-colors"
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
        <div className="flex items-center justify-center gap-1.5 px-page py-1.5 bg-chat-accent/10 border-b border-chat-accent/30 text-body3 text-chat-accent text-center">
          <Wifi className="h-3.5 w-3.5" />
          {connection === "offline" ? "网络已断开，正在等待重新连接…" : "正在重新连接…"}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-chat-accent/10 text-body3 text-chat-accent text-center">
          您今日用量已达 {limitPct}%，建议核心问题尽快咨询。
        </div>
      )}
    </>
  );
}

const SUGGESTIONS = ["我的卡为什么被锁了？", "如何对接 Open API？", "查一下我最近的订单"];

export function Suggestions({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="px-page pb-2 flex flex-wrap gap-2">
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          onClick={() => onPick(s)}
          className="rounded-full glass border border-chat-primary/20 px-4 py-1.5 text-body3 text-chat-primary hover:bg-chat-primary/10 transition-colors"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（ChatWindow.test 的 header 文案、Suggestions 文案不变）。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ChatExtras.tsx
git commit -m "feat(chat): Header/状态条/建议词 深色玻璃化"
```

---

### Task 4: MessageBubble（含深色 markdown）

**Files:**
- Modify: `web/src/components/MessageBubble.tsx`（整文件）

- [ ] **Step 1: 用以下完整内容替换 `MessageBubble.tsx`**

边框只加在 `AvatarFallback` 的 className 上（现有用法已证明其透传 className）。保留 `思考中…`、`ToolCallChip`、所有 content 渲染。

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
        <div
          className="max-w-[80%] rounded-2xl rounded-tr-none bg-gradient-to-r from-[#0891B2] to-[#22D3EE] text-chat-on-primary px-4 py-3 text-body1 font-medium whitespace-pre-wrap"
          style={{ boxShadow: "0 4px 14px rgba(34,211,238,0.2)" }}
        >
          {m.content}
        </div>
      </div>
    );
  }
  if (m.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="text-footnote text-chat-on-surface-variant/60 py-1 px-3 rounded-full bg-chat-surface-variant/30 border border-white/5">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "human_agent") {
    return (
      <div className="flex gap-3 items-start">
        <Avatar>
          <AvatarFallback className="bg-chat-accent/20 text-chat-accent font-bold border-2 border-chat-accent/40">
            客
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[85%]">
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-footnote font-bold text-chat-accent">
              客服 {m.display_name ?? ""}
            </span>
            <BadgeCheck className="h-3 w-3 text-chat-accent/80" />
            <span className="text-footnote text-chat-on-surface-variant/60">· 已认证</span>
          </div>
          <div className="glass amber-glow-border rounded-xl rounded-tl-none px-4 py-3 text-body1 text-chat-on-surface/90 whitespace-pre-wrap">
            {m.content}
          </div>
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-3 items-start">
      <Avatar>
        <AvatarFallback className="bg-chat-surface-variant text-chat-primary border-2 border-chat-primary/30">
          AI
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 max-w-[85%] glass cyan-glow-border rounded-xl rounded-tl-none px-4 py-3 space-y-2">
        {(m.tool_calls ?? []).map((tc, i) => (
          <ToolCallChip key={i} tc={tc} userType={userType} />
        ))}
        <div className="markdown-body-dark text-chat-on-surface/90">
          {m.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          ) : (
            <span className="text-chat-on-surface-variant text-body2">思考中…</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（components.test 的 `你好啊`、`欢迎`、`思考中…`、`结论` 等仍命中）。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MessageBubble.tsx
git commit -m "feat(chat): 消息气泡深色化（用户渐变/AI玻璃/人工琥珀）"
```

---

### Task 5: ToolCallChip

**Files:**
- Modify: `web/src/components/ToolCallChip.tsx`（整文件）

- [ ] **Step 1: 用以下完整内容替换 `ToolCallChip.tsx`**

保留 `C_LABELS` 全部映射、C 端语言化逻辑、B 端展开 `tc.name`/JSON 行为。

```tsx
import { Check, ChevronRight, Loader2, Wrench, X } from "lucide-react";
import { useState } from "react";

import { cn } from "../lib/utils";
import type { ToolCallShown } from "../types";

// C 端语言化：不暴露内部工具名/JSON（spec §6.2）。
const C_LABELS: Record<string, string> = {
  query_user: "正在查询账户信息…",
  query_card: "正在查询卡片状态…",
  query_balance: "正在查询余额…",
  query_kyc: "正在查询认证状态…",
  query_transaction: "正在查询交易记录…",
  query_bu_order: "正在查询订单…",
  query_bu_request_log: "正在查询接口调用记录…",
  search_code: "正在排查问题…",
  read_file: "正在排查问题…",
  lookup_api_doc: "正在查阅接口文档…",
  create_ticket: "正在为您创建工单…",
};

function statusIcon(ok: boolean | undefined) {
  return ok === undefined ? Loader2 : ok ? Check : X;
}

/** C 端：仅显示语言化进度，不暴露工具名/JSON（spec §6.2）。 */
function CToolChip({ tc }: { tc: ToolCallShown }) {
  const Icon = statusIcon(tc.ok);
  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-chat-primary/10 border border-chat-primary/20 text-chat-primary text-body3">
      <Icon className={cn("h-3 w-3", tc.ok === undefined && "animate-spin")} />
      <span>{C_LABELS[tc.name] ?? "正在为您处理…"}</span>
    </div>
  );
}

export function ToolCallChip({ tc, userType = "b" }: { tc: ToolCallShown; userType?: "c" | "b" }) {
  const [open, setOpen] = useState(false);

  if (userType === "c") return <CToolChip tc={tc} />;

  const Icon = statusIcon(tc.ok);
  const color =
    tc.ok === undefined
      ? "text-chat-on-surface-variant"
      : tc.ok
        ? "text-status-success"
        : "text-status-error";

  return (
    <div className="rounded bg-chat-surface-variant/50">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-body3 text-chat-on-surface-variant hover:bg-chat-surface-variant rounded transition-colors"
      >
        <Wrench className="h-3.5 w-3.5" />
        <span className="flex-1 text-left font-mono">{tc.name}</span>
        <Icon className={cn("h-3.5 w-3.5", color, tc.ok === undefined && "animate-spin")} />
        <ChevronRight
          className={cn("h-3.5 w-3.5 transition-transform duration-300", open && "rotate-90")}
        />
      </button>
      {open && (
        <pre className="px-2 pb-2 text-body4 text-chat-on-surface-variant font-mono overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify(tc.input, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（identityAndChips.test 的 `正在查询卡片状态…`/`query_card`、components.test 的 `query_user` 展开 `user_id` 行为不变）。

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ToolCallChip.tsx
git commit -m "feat(chat): 工具调用 chip 深色 cyan 化"
```

---

### Task 6: TicketCard + TicketStatusBanner

**Files:**
- Modify: `web/src/components/TicketCard.tsx`（整文件）
- Modify: `web/src/components/TicketStatusBanner.tsx:16-21`

- [ ] **Step 1: 用以下完整内容替换 `TicketCard.tsx`**

改用原生元素（去掉 `ui/card`、`ui/button` 依赖以贴合深色样式）。保留 `statusLabel`、`已解决`/`未解决` 文案、`status === "resolved"` 才显示按钮的逻辑。

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
    <div className="glass cyan-glow-border rounded-xl overflow-hidden relative">
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-chat-primary/40 to-transparent" />
      <div className="flex items-center gap-2 px-page py-block-sm border-b border-white/5 bg-white/5 text-body3">
        <Ticket className="h-3.5 w-3.5 text-chat-primary" />
        <span className="font-mono text-chat-on-surface-variant">{externalId}</span>
        <span className="ml-auto px-2 py-0.5 rounded-full bg-chat-primary/10 text-chat-primary text-footnote font-bold border border-chat-primary/20">
          {statusLabel(status)}
        </span>
      </div>
      <div className="px-page py-block-sm space-y-3">
        <div className="text-body2 text-chat-on-surface/90">{summary}</div>
        {status === "resolved" && (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={onConfirm}
              className="flex items-center justify-center gap-1 bg-chat-primary text-chat-on-primary text-body3 font-bold py-2.5 rounded-lg active:scale-95 transition-all"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </button>
            <button
              onClick={onReject}
              className="flex items-center justify-center gap-1 border border-chat-on-surface-variant/30 text-chat-on-surface-variant text-body3 font-bold py-2.5 rounded-lg active:scale-95 transition-all hover:bg-white/5"
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

- [ ] **Step 2: 改 `TicketStatusBanner.tsx` 的呈现 `<div>`**

把：

```tsx
    <div className="px-page py-2 bg-surface-subtle text-body3 text-ink-secondary border-b border-line">
```

替换为：

```tsx
    <div className="px-page py-2 glass border-b border-white/5 text-body3 text-chat-on-surface-variant">
```

- [ ] **Step 3: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（components.test 的 `等待受理`、`已解决`/`未解决` 点击触发 onConfirm/onReject、pending 时 `queryByText("已解决")` 为 null 均不变）。

- [ ] **Step 4: Commit**

```bash
git add web/src/components/TicketCard.tsx web/src/components/TicketStatusBanner.tsx
git commit -m "feat(chat): 工单卡片/状态条深色玻璃化"
```

---

### Task 7: InputBox + HandoffButton

**Files:**
- Modify: `web/src/components/InputBox.tsx`（整文件）
- Modify: `web/src/components/HandoffButton.tsx`（整文件）

- [ ] **Step 1: 用以下完整内容替换 `InputBox.tsx`**

发送键改原生 `button`（避免 `ui/button` 默认背景与 cyan 冲突）。**保留 `placeholder` prop 默认值与 `aria-label="发送"`、Enter 提交逻辑。**

```tsx
import { Send } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

export function InputBox({
  onSend,
  disabled,
  placeholder = "描述你的问题…",
}: {
  onSend: (t: string) => void;
  disabled: boolean;
  placeholder?: string;
}) {
  const [v, setV] = useState("");

  function submit() {
    const text = v.trim();
    if (text && !disabled) {
      onSend(text);
      setV("");
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-chat-primary/10 glass px-page py-block-sm safe-bottom">
      <div className="flex items-end gap-2 rounded-2xl bg-chat-surface-variant/50 border border-white/5 px-3 py-2 transition-all focus-within:border-chat-primary/50 focus-within:ring-1 focus-within:ring-chat-primary/20">
        <textarea
          value={v}
          rows={1}
          placeholder={placeholder}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={onKey}
          className="flex-1 resize-none bg-transparent text-body1 text-chat-on-surface placeholder:text-chat-on-surface-variant/40 outline-none max-h-32"
        />
        <button
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="grid h-10 w-10 place-items-center rounded-xl bg-chat-primary text-chat-on-primary transition-transform active:scale-90 disabled:opacity-50"
          style={{ boxShadow: "0 0 15px rgba(34,211,238,0.3)" }}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 用以下完整内容替换 `HandoffButton.tsx`**

**保留文案 `没解决？转人工 →`。**

```tsx
import { Headphones } from "lucide-react";

/**
 * "没解决？转人工 →" 按钮。点击调 useChat.requestHandoff →
 * POST /request-human（置 human_pending + 建人工介入工单，spec §13.7）。
 */
export function HandoffButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <div className="px-page py-2">
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-full glass border border-white/10 text-body2 text-chat-on-surface-variant transition-all hover:border-chat-primary/40 hover:text-chat-primary disabled:opacity-50"
      >
        <Headphones className="h-4 w-4" />
        没解决？转人工 →
      </button>
    </div>
  );
}
```

- [ ] **Step 3: 验证**

Run: `pnpm typecheck && pnpm test:ci`
Expected: PASS（ChatWindow.test 的 `findByPlaceholderText("描述你的问题…")`、`getByLabelText("发送")`；components.test 的 `没解决？转人工 →` 点击均不变）。

- [ ] **Step 4: Commit**

```bash
git add web/src/components/InputBox.tsx web/src/components/HandoffButton.tsx
git commit -m "feat(chat): 输入框/转人工按钮深色玻璃化"
```

---

### Task 8: 全量验证收尾

**Files:** 无新增改动，仅校验。

- [ ] **Step 1: 全量类型 + 测试 + 构建**

Run: `pnpm typecheck && pnpm test:ci && pnpm build`
Expected: 全 PASS。

- [ ] **Step 2: 格式与 lint**

Run: `pnpm format && pnpm lint`
Expected: format 写入无遗留、lint 0 warning。

- [ ] **Step 3: 人工核对（启动 dev 看真机效果）**

Run: `pnpm dev`，浏览器移动端视图打开 C 端聊天，逐项确认：深色底+网格、Header cyan logo+呼吸点、AI 玻璃气泡、用户 cyan 渐变气泡、人工琥珀气泡、工单卡 cyan 顶光线、建议 chips、转人工按钮、底部 cyan 发送输入框；确认**没有**多余的底部 tab 导航栏。
Expected: 视觉符合 Stitch 设计；其他端（工作台/登录/后台）打开仍为原浅色，未受影响。

- [ ] **Step 4: Commit（若 format 有改动）**

```bash
git add -A web/
git commit -m "chore(chat): 格式化收尾"
```

---

## Self-Review 记录

- **Spec 覆盖：** §2 token → Task1；§3 隔离方案 → Task1；§4 逐组件（ChatWindow/MessageList→T2、ChatExtras→T3、MessageBubble→T4、ToolCallChip→T5、TicketCard/Banner→T6、InputBox/HandoffButton→T7）；§4 去掉底部 tab → 本就不在现有组件中，T8 Step3 核对确认未引入；§5 测试锚点 → 每个相关任务的验证步骤显式列出；§6 工程约束 → T8。无遗漏。
- **占位符扫描：** 无 TBD/TODO，每个改动均给完整代码。
- **类型一致：** 各组件 props 签名与现有保持一致（未改 props）；新增 `chat-*` 类名与 `globals.css` 自定义类名（`.glass/.cyan-glow-border/.amber-glow-border/.grid-bg/.animate-breathe/.markdown-body-dark`）在 Task1 定义、后续任务引用，命名一致。
- **图标：** 新用 lucide 图标 `Wifi`(T3)、`BadgeCheck`(T4)、`Headphones`(T7) 均为 lucide-react 标准导出；其余沿用现有导入。
