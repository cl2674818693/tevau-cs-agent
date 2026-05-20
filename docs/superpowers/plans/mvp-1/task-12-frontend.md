# Task 12: React 前端骨架（Vite + TS + Tailwind + shadcn/ui + APP 设计系统）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**接入 Tevau APP 设计系统**：源文档 `tevau-pay-flutter/docs/UI_DESIGN_SYSTEM.md`。把色系（品牌色 `#C8F833` 荧光绿、深色 `#042834` 等）、字阶（Source Sans 3 全 13 档）、圆角、间距、动画完整映射到 Tailwind theme，让 webview 视觉与 APP 一致。前端组件用 shadcn/ui 风格（自有源码、可定制）；AI 输出走 react-markdown 渲染。

**对齐 spec 修订（MVP-1 必做）**：
- §6.2 会话初始化：首屏先 `POST /api/v1/conversations` 拿 `{conversation_id, user_type, display_name, greeting, limits}` 再开 SSE
- §3.3 SSE 主链路改 `GET /api/v1/chat?conversation_id=...&message=...`；事件类型 = `conversation` / `message_start` / `content_block_delta` / `tool_use` / `tool_result` / `message_stop` / `error` / `warning` / `ping`；客户端 60s 无任何事件视为断线，重连用 `Last-Event-ID` 头
- §3.3 取消生成：用户点"停止生成" → `DELETE /api/v1/chat/{conversation_id}/stream`
- §13.7 + §11 line 551 转人工：每条 AI 回复底部固定按钮 `没解决？转人工 →`，点击后**前端发送一条固定 user message** `"我想转人工"` 进对话流，AI 通过 prompt 识别意图自动建工单。**MVP-1 不调 `/request-human` 端点**。

**Files:**
- Create: `web/package.json` / `web/tsconfig.json` / `web/vite.config.ts` / `web/index.html`
- Create: `web/postcss.config.js` / `web/tailwind.config.ts`
- Create: `web/eslint.config.js` / `web/.prettierrc.json` / `web/.prettierignore`
- Create: `web/src/main.tsx` / `web/src/App.tsx` / `web/src/types.ts`
- Create: `web/src/styles/globals.css`
- Create: `web/src/lib/utils.ts`（shadcn `cn()`）
- Create: `web/src/hooks/useChat.ts` / `web/src/hooks/useVisualViewport.ts`
- Create: `web/src/api/chat.ts`
- Create: `web/src/components/ui/button.tsx`
- Create: `web/src/components/ui/card.tsx`
- Create: `web/src/components/ui/avatar.tsx`
- Create: `web/src/components/ChatWindow.tsx`
- Create: `web/src/components/MessageList.tsx`
- Create: `web/src/components/MessageBubble.tsx`
- Create: `web/src/components/ToolCallChip.tsx`
- Create: `web/src/components/TicketCard.tsx`
- Create: `web/src/components/InputBox.tsx`
- Create: `web/src/components/HandoffButton.tsx`（spec §13.7 转人工按钮）
- Create: `web/tests/useChat.test.ts` / `web/tests/ChatWindow.test.tsx`

- [ ] **Step 1: 写 `web/package.json`**（含 ESLint + Prettier，对齐 Task 0 工程规范）

```json
{
  "name": "ai-engine-web",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest",
    "preview": "vite preview",
    "lint": "eslint . --max-warnings=0",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write .",
    "format:check": "prettier --check .",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",

    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4",
    "class-variance-authority": "^0.7.0",
    "@radix-ui/react-slot": "^1.1.0",
    "@radix-ui/react-tooltip": "^1.1.4",
    "@radix-ui/react-dialog": "^1.1.2",
    "@radix-ui/react-avatar": "^1.1.1",
    "lucide-react": "^0.460.0",

    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0",
    "shiki": "^1.22.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^8.4.0",
    "@typescript-eslint/parser": "^8.4.0",
    "@vitejs/plugin-react": "^4.3.1",
    "eslint": "^9.9.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-react": "^7.35.0",
    "eslint-plugin-react-hooks": "^5.1.0",
    "jsdom": "^25.0.0",
    "prettier": "^3.3.3",
    "prettier-plugin-tailwindcss": "^0.6.8",
    "typescript": "^5.5.4",
    "typescript-eslint": "^8.4.0",
    "vite": "^5.4.2",
    "vitest": "^2.0.5",
    "@vitest/coverage-v8": "^2.0.5",

    "tailwindcss": "^3.4.14",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss-animate": "^1.0.7"
  }
}
```

并把 `test` 脚本改为带覆盖率：
```json
"test": "vitest --coverage",
"test:ci": "vitest run --coverage"
```

- [ ] **Step 1.1: 写 `web/eslint.config.js`**（flat config）

```js
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettier from "eslint-config-prettier";

export default [
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}", "tests/**/*.{ts,tsx}"],
    plugins: { react, "react-hooks": reactHooks },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "react/jsx-uses-react": "off",
      "react/react-in-jsx-scope": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "max-lines": ["warn", { max: 250, skipBlankLines: true, skipComments: true }],
      "max-lines-per-function": ["warn", { max: 80, skipBlankLines: true, skipComments: true }],
      "complexity": ["warn", 10],
    },
    settings: { react: { version: "detect" } },
  },
  prettier,   // 关掉与 prettier 冲突的规则
  { ignores: ["dist", "node_modules", "*.config.js"] },
];
```

- [ ] **Step 1.2: 写 `web/.prettierrc.json`**

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2,
  "arrowParens": "always"
}
```

- [ ] **Step 1.3: 写 `web/.prettierignore`**

```
dist
node_modules
coverage
*.lock
```

- [ ] **Step 2: 写 `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: 写 `web/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "cobertura"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/**/*.d.ts", "tests/**"],
      thresholds: {
        lines: 75,
        functions: 75,
        branches: 70,
        statements: 75,
        autoUpdate: false,
      },
    },
  },
});
```

- [ ] **Step 3.1: 写 `web/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3.2: 写 `web/tailwind.config.ts`**（接入 Tevau APP 设计系统）

源文档：`tevau-pay-flutter/docs/UI_DESIGN_SYSTEM.md`。把 APP 的色系、字阶、圆角、间距、动画一一映射到 Tailwind theme。

```ts
import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // —— Tevau 品牌色（UI_DESIGN_SYSTEM §1 品牌色） ——
        brand: {
          DEFAULT: "#C8F833",     // 主品牌（标志性荧光绿）
          dark: "#042834",        // 次品牌
          tab: "#D9F490",         // tab 滑块
          press: "#305500",       // 按下 / 链接 / 必填星号
          disabled: "#F0F1F3",
        },
        // —— 文字色（§1） ——
        ink: {
          primary: "#121212",
          secondary: "#8C939C",
          placeholder: "#4B5563",
          subtle: "#6C737C",
          footnote: "#AEB3BA",
        },
        // —— 背景与边框 ——
        surface: {
          page: "#FEFEFE",
          card: "#FFFFFF",
          subtle: "#F6F6F6",
          container: "#F0F1F3",
          disabled: "#EFEFEF",
        },
        line: "#E0E3E7",
        // —— 功能色（§1） ——
        status: {
          error: "#ED3241",
          success: "#51B832",
          warning: "#F59E0B",
        },
        // shadcn/ui 兼容（直接映射到 brand/ink/surface）
        background: "#FEFEFE",
        foreground: "#121212",
        primary: { DEFAULT: "#C8F833", foreground: "#121212" },
        secondary: { DEFAULT: "#042834", foreground: "#FFFFFF" },
        muted: { DEFAULT: "#F0F1F3", foreground: "#8C939C" },
        accent: { DEFAULT: "#D9F490", foreground: "#121212" },
        destructive: { DEFAULT: "#ED3241", foreground: "#FFFFFF" },
        border: "#E0E3E7",
        input: "#E0E3E7",
        ring: "#C8F833",
        card: { DEFAULT: "#FFFFFF", foreground: "#121212" },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', "-apple-system", "PingFang SC", "sans-serif"],
      },
      // —— 字阶（§2 完整 13 档对齐 APP） ——
      fontSize: {
        h0:       ["32px", { lineHeight: "36px", fontWeight: "800" }],
        h1:       ["32px", { lineHeight: "36px", fontWeight: "800" }],
        h2:       ["28px", { lineHeight: "32px", fontWeight: "700" }],
        sh0:      ["24px", { lineHeight: "28px", fontWeight: "700" }],
        sh1:      ["18px", { lineHeight: "28px", fontWeight: "700" }],
        sh2:      ["16px", { lineHeight: "20px", fontWeight: "700" }],
        sh3:      ["16px", { lineHeight: "20px", fontWeight: "600" }],
        body0:    ["14px", { lineHeight: "18px", fontWeight: "700" }],
        body1:    ["14px", { lineHeight: "18px", fontWeight: "600" }],
        body2:    ["14px", { lineHeight: "18px", fontWeight: "400" }],
        body3:    ["12px", { lineHeight: "16px", fontWeight: "600" }],
        body4:    ["12px", { lineHeight: "16px", fontWeight: "500" }],
        body5:    ["12px", { lineHeight: "16px", fontWeight: "400" }],
        footnote: ["10px", { lineHeight: "12px", fontWeight: "400" }],
      },
      // —— 圆角（§5） ——
      borderRadius: {
        sm: "8px",        // 验证码/小按钮/tab 滑块
        DEFAULT: "12px",  // 输入框/主按钮/tab容器/社交按钮
        lg: "16px",       // 卡片/弹窗
      },
      // —— 间距（§3，常用别名） ——
      spacing: {
        "page": "16px",       // 页面水平内边距
        "block-sm": "8px",
        "block-lg": "16px",
        "input-x": "12px",
        "input-y": "16px",
      },
      // —— 动画时长（§6） ——
      transitionDuration: {
        250: "250ms",
        300: "300ms",
        400: "400ms",
      },
      transitionTimingFunction: {
        "out-cubic": "cubic-bezier(0.215, 0.61, 0.355, 1)",
        "in-cubic":  "cubic-bezier(0.55, 0.055, 0.675, 0.19)",
        "out-back":  "cubic-bezier(0.34, 1.56, 0.64, 1)",   // tab 切换用
      },
      // —— 聚焦发光（§1 输入框聚焦） ——
      boxShadow: {
        focus: "0 0 8px 0 rgba(200, 248, 51, 0.15)",
      },
      backgroundImage: {
        "page-gradient": "linear-gradient(180deg, #F6F6F6 0%, #FEFEFE 100%)",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
```

- [ ] **Step 3.3: 写 `web/src/styles/globals.css`**（替代旧 `web/src/styles.css`）

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* —— 字体（CDN 加载 Source Sans 3，与 APP 一致） —— */
@import url("https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700;800&display=swap");

/* —— 基础 —— */
html, body, #root {
  height: 100%;
}

body {
  font-family: "Source Sans 3", -apple-system, "PingFang SC", sans-serif;
  background-image: linear-gradient(180deg, #F6F6F6 0%, #FEFEFE 100%);
  background-attachment: fixed;
  color: #121212;
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}

/* —— 移动端 webview 安全区适配 —— */
.safe-top { padding-top: env(safe-area-inset-top); }
.safe-bottom { padding-bottom: env(safe-area-inset-bottom); }

/* —— 工具类：聚焦发光（对齐 APP 输入框） —— */
.focus-glow:focus-within {
  box-shadow: 0 0 8px 0 rgba(200, 248, 51, 0.15);
  border-color: #C8F833 !important;
  border-width: 1.2px !important;
  transition: all 250ms;
}

/* —— Markdown 渲染样式 —— */
.markdown-body {
  font-size: 14px;
  line-height: 1.6;
}
.markdown-body p { margin: 0 0 8px 0; }
.markdown-body p:last-child { margin-bottom: 0; }
.markdown-body strong { font-weight: 700; color: #121212; }
.markdown-body ul, .markdown-body ol { padding-left: 20px; margin: 8px 0; }
.markdown-body li { margin: 2px 0; }
.markdown-body code {
  background: #F0F1F3;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: ui-monospace, "SF Mono", monospace;
  font-size: 13px;
}
.markdown-body pre {
  background: #042834;
  color: #fff;
  padding: 12px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: 13px;
}
.markdown-body pre code { background: transparent; color: inherit; padding: 0; }
.markdown-body blockquote {
  border-left: 3px solid #C8F833;
  padding-left: 12px;
  color: #6C737C;
  margin: 8px 0;
}
```

- [ ] **Step 3.4: 写 `web/src/lib/utils.ts`**（shadcn `cn()` 工具函数）

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3.5: 写 `web/src/hooks/useVisualViewport.ts`**（移动端键盘弹起不挡输入框）

```ts
import { useEffect, useState } from "react";

/**
 * 监听虚拟键盘弹起。在 iOS Safari / Android webview 里键盘弹起时
 * window.innerHeight 不变，需要用 visualViewport.height 才能得到
 * 实际可见区域。返回 bottomInset = innerHeight - visualViewport.height。
 */
export function useKeyboardInset(): number {
  const [inset, setInset] = useState(0);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      const next = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      setInset(next);
    };
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    update();
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, []);
  return inset;
}
```

- [ ] **Step 4: 写 `web/index.html`**（加 viewport-fit + 字体预连接）

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no" />
    <meta name="theme-color" content="#C8F833" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <title>Tevau AI 客服</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: 写 `web/src/types.ts`**

```ts
// SSE 事件类型，对齐 spec §3.3 表
export type ChatEvent = ({
  _eventId?: string;     // 来自 SSE 的 id: 字段，用于断线重连 Last-Event-ID
}) & (
  | { type: "conversation"; conversation_id: number; user_type: "c" | "b"; model: string }
  | { type: "message_start"; message_id: string }
  | { type: "content_block_delta"; index: number; delta: { type: "text_delta"; text: string } }
  | { type: "tool_use"; tool_use_id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id: string; output: unknown; is_error: boolean }
  | { type: "message_stop"; stop_reason: string; usage?: Record<string, unknown> }
  | { type: "ticket_event"; [k: string]: unknown }
  | { type: "mode_change"; from: string; to: string; by_staff_id?: string }
  | { type: "human_message"; message_id: string; sender_staff_id: string; display_name: string; content: string }
  | { type: "error"; code: string; message: string; retry_after_ms?: number }
  | { type: "warning"; pct?: number; [k: string]: unknown }
);

// 会话初始化端点响应（spec §6.2）
export type ConversationInit = {
  conversation_id: number;
  user_type: "c" | "b";
  display_name: string;
  greeting: string;
  history_url: string | null;
  limits: { daily_token_used_pct: number; max_turns: number };
};

export type Message =
  | { role: "system"; content: string }
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; tool_calls?: ToolCallShown[] };

export type ToolCallShown = {
  name: string;
  input: Record<string, unknown>;
  ok?: boolean;
};
```

- [ ] **Step 6: 写 `web/src/api/chat.ts`**

```ts
import type { ChatEvent, ConversationInit } from "../types";

/**
 * 会话初始化（spec §6.2）。首屏调一次，拿 user_type / display_name / greeting / limits。
 */
export async function initConversation(buId: string): Promise<ConversationInit> {
  const resp = await fetch("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-BU-ID": buId },
    body: JSON.stringify({}),
  });
  if (!resp.ok) throw new Error(`init http ${resp.status}`);
  return resp.json();
}

/**
 * SSE 主链路（spec §3.3）。GET 请求 + 携带 Last-Event-ID（断线重连后由 caller 传入）。
 * 事件类型见 spec §3.3 表：conversation / message_start / content_block_delta /
 * tool_use / tool_result / message_stop / error / warning / ping。
 */
export async function* streamChat(args: {
  conversationId: number;
  message: string;
  buId: string;
  lastEventId?: string;
}): AsyncGenerator<ChatEvent> {
  const url = `/api/v1/chat?conversation_id=${args.conversationId}&message=${encodeURIComponent(args.message)}`;
  const headers: Record<string, string> = { "X-BU-ID": args.buId };
  if (args.lastEventId) headers["Last-Event-ID"] = args.lastEventId;
  const resp = await fetch(url, { headers });
  if (!resp.ok || !resp.body) throw new Error(`chat http ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const eventLine = frame.split("\n").find(l => l.startsWith("event:"));
      const dataLine = frame.split("\n").find(l => l.startsWith("data:"));
      const idLine = frame.split("\n").find(l => l.startsWith("id:"));
      if (!eventLine || !dataLine) continue;
      const eventName = eventLine.slice("event:".length).trim();
      if (eventName === "ping") continue;       // 心跳直接跳过
      const json = dataLine.slice("data:".length).trim();
      try {
        const data = JSON.parse(json);
        yield { type: eventName, ...data, _eventId: idLine?.slice("id:".length).trim() } as ChatEvent;
      } catch { /* ignore parse error */ }
    }
  }
}

/**
 * 取消生成（spec §3.3）。用户点"停止生成"按钮调。
 */
export async function cancelStream(conversationId: number, buId: string): Promise<void> {
  await fetch(`/api/v1/chat/${conversationId}/stream`, {
    method: "DELETE",
    headers: { "X-BU-ID": buId },
  });
}
```

- [ ] **Step 7: 写 `web/src/hooks/useChat.ts`**

```ts
import { useCallback, useEffect, useState } from "react";
import { initConversation, streamChat, cancelStream } from "../api/chat";
import type { Message, ToolCallShown, ConversationInit } from "../types";

const BU_ID = "BU00243780"; // MVP-1 写死，MVP-2 接 SSO/JWT

// spec §13.7 + §11 line 551：MVP-1"转人工"按钮发的固定文本
export const HANDOFF_TRIGGER_TEXT = "我想转人工";

export function useChat() {
  const [init, setInit] = useState<ConversationInit | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [lastEventId, setLastEventId] = useState<string | undefined>();

  // 首屏调 init（spec §6.2）拿 conversation_id + greeting
  useEffect(() => {
    initConversation(BU_ID).then(info => {
      setInit(info);
      setMessages([{ role: "system", content: info.greeting }]);
    }).catch(e => console.error("init failed", e));
  }, []);

  const send = useCallback(async (text: string) => {
    if (!init) return;
    setSending(true);
    setMessages(prev => [...prev, { role: "user", content: text }]);
    const assistant: Message = { role: "assistant", content: "", tool_calls: [] };
    setMessages(prev => [...prev, assistant]);

    try {
      for await (const ev of streamChat({
        conversationId: init.conversation_id, message: text, buId: BU_ID,
        lastEventId,
      })) {
        if (ev._eventId) setLastEventId(ev._eventId);
        switch (ev.type) {
          case "content_block_delta": {
            const text = ev.delta?.text ?? "";
            setMessages(prev => {
              const last = prev[prev.length - 1];
              const next = { ...last, content: (last as any).content + text } as Message;
              return [...prev.slice(0, -1), next];
            });
            break;
          }
          case "tool_use": {
            const tc: ToolCallShown = { name: ev.name, input: ev.input };
            setMessages(prev => {
              const last = prev[prev.length - 1] as Extract<Message, { role: "assistant" }>;
              return [...prev.slice(0, -1),
                      { ...last, tool_calls: [...(last.tool_calls ?? []), tc] }];
            });
            break;
          }
          case "tool_result": {
            setMessages(prev => {
              const last = prev[prev.length - 1] as Extract<Message, { role: "assistant" }>;
              const calls = (last.tool_calls ?? []).slice();
              const i = calls.length - 1;
              if (i >= 0) calls[i] = { ...calls[i], ok: !ev.is_error };
              return [...prev.slice(0, -1), { ...last, tool_calls: calls }];
            });
            break;
          }
          case "error":   // spec §3.3 错误码：AUTH_EXPIRED / RATE_LIMITED / ... 由 UI 状态层处理（task-12 §13.6）
            console.warn("sse error", ev);
            break;
          case "warning": // 80% token 阈值
            console.warn("sse warning", ev);
            break;
          // message_start / message_stop / conversation：仅记录，不直接渲染
        }
      }
    } finally {
      setSending(false);
    }
  }, [init, lastEventId]);

  // spec §13.7 + §11 line 551："没解决？转人工"按钮 onClick
  const requestHandoff = useCallback(() => send(HANDOFF_TRIGGER_TEXT), [send]);

  // spec §3.3 取消生成
  const stop = useCallback(() => {
    if (init) cancelStream(init.conversation_id, BU_ID);
  }, [init]);

  return { messages, sending, send, requestHandoff, stop, init };
}
```

- [ ] **Step 8.1: 写 shadcn 基础组件**（最小集 — Button / Card / Avatar）

`web/src/components/ui/button.tsx`:
```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded font-body0 transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 " +
  "disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-brand text-ink-primary hover:bg-brand-tab active:bg-brand-press active:text-white",
        secondary: "bg-brand-dark text-white hover:opacity-90",
        ghost: "hover:bg-surface-container text-ink-primary",
        link: "text-brand-press underline-offset-4 hover:underline",
      },
      size: {
        lg: "h-12 px-page text-body0",   // 48px 主按钮
        md: "h-9 px-3 text-body3",        // 36px 小按钮
        sm: "h-8 px-2 text-body4",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "lg" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp ref={ref} className={cn(buttonVariants({ variant, size, className }))} {...props} />;
  },
);
Button.displayName = "Button";
export { buttonVariants };
```

`web/src/components/ui/card.tsx`:
```tsx
import * as React from "react";
import { cn } from "../../lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...p }, ref) => (
    <div ref={ref} className={cn("rounded-lg bg-surface-card border border-line", className)} {...p} />
  ),
);
Card.displayName = "Card";

export const CardHeader = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("px-page py-block-sm border-b border-line", className)} {...p} />
);

export const CardContent = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("px-page py-block-sm", className)} {...p} />
);
```

`web/src/components/ui/avatar.tsx`:
```tsx
import * as React from "react";
import * as AvatarPrimitive from "@radix-ui/react-avatar";
import { cn } from "../../lib/utils";

export const Avatar = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>
>(({ className, ...p }, ref) => (
  <AvatarPrimitive.Root ref={ref}
    className={cn("relative flex h-8 w-8 shrink-0 overflow-hidden rounded-full", className)} {...p} />
));
Avatar.displayName = AvatarPrimitive.Root.displayName;

export const AvatarImage = AvatarPrimitive.Image;
export const AvatarFallback = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Fallback>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(({ className, ...p }, ref) => (
  <AvatarPrimitive.Fallback ref={ref}
    className={cn("flex h-full w-full items-center justify-center bg-brand text-ink-primary text-body3",
                  className)} {...p} />
));
AvatarFallback.displayName = "AvatarFallback";
```

- [ ] **Step 8.2: 写消息组件（含 markdown 渲染）**

`web/src/components/MessageBubble.tsx`:
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ToolCallChip } from "./ToolCallChip";
import type { Message } from "../types";
import { cn } from "../lib/utils";

export function MessageBubble({ m }: { m: Message }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded bg-brand text-ink-primary px-3 py-2 text-body1 whitespace-pre-wrap">
          {m.content}
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-2 items-start">
      <Avatar>
        <AvatarFallback>AI</AvatarFallback>
      </Avatar>
      <div className={cn(
        "flex-1 max-w-[80%] rounded-lg bg-surface-card border border-line",
        "px-page py-block-sm space-y-2"
      )}>
        {(m.tool_calls ?? []).map((tc, i) => <ToolCallChip key={i} tc={tc} />)}
        <div className="markdown-body">
          {m.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          ) : (
            <span className="text-ink-secondary text-body2">思考中…</span>
          )}
        </div>
      </div>
    </div>
  );
}
```

`web/src/components/ToolCallChip.tsx`:
```tsx
import { useState } from "react";
import { Wrench, Check, X, Loader2, ChevronRight } from "lucide-react";
import type { ToolCallShown } from "../types";
import { cn } from "../lib/utils";

export function ToolCallChip({ tc }: { tc: ToolCallShown }) {
  const [open, setOpen] = useState(false);
  const Icon = tc.ok === undefined ? Loader2 : tc.ok ? Check : X;
  const color = tc.ok === undefined ? "text-ink-secondary"
              : tc.ok ? "text-status-success" : "text-status-error";

  return (
    <div className="rounded bg-surface-container">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-body3 text-ink-subtle hover:bg-brand-disabled rounded transition-colors"
      >
        <Wrench className="h-3.5 w-3.5" />
        <span className="flex-1 text-left font-mono">{tc.name}</span>
        <Icon className={cn("h-3.5 w-3.5", color, tc.ok === undefined && "animate-spin")} />
        <ChevronRight className={cn("h-3.5 w-3.5 transition-transform duration-300", open && "rotate-90")} />
      </button>
      {open && (
        <pre className="px-2 pb-2 text-body4 text-ink-subtle font-mono overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify(tc.input, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

`web/src/components/TicketCard.tsx`:
```tsx
import { Ticket, CheckCircle2, XCircle } from "lucide-react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";

export function TicketCard({
  externalId, summary, status = "pending", onConfirm, onReject,
}: {
  externalId: string;
  summary: string;
  status?: "pending" | "assigned" | "in_progress" | "resolved" | "closed";
  onConfirm?: () => void;
  onReject?: () => void;
}) {
  return (
    <Card className="border-warning/30 bg-yellow-50/40">
      <div className="px-page py-block-sm space-y-1">
        <div className="flex items-center gap-2 text-body3 text-ink-subtle">
          <Ticket className="h-3.5 w-3.5" />
          <span className="font-mono">{externalId}</span>
          <span className="ml-auto">{statusLabel(status)}</span>
        </div>
        <div className="text-body1 text-ink-primary">{summary}</div>
        {status === "resolved" && (
          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="primary" onClick={onConfirm}>
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </Button>
            <Button size="sm" variant="ghost" onClick={onReject}>
              <XCircle className="h-3.5 w-3.5" /> 未解决
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

function statusLabel(s: string) {
  return {
    pending: "等待受理",
    assigned: "已分派",
    in_progress: "处理中",
    resolved: "已处理",
    closed: "已关闭",
  }[s] ?? s;
}
```

`web/src/components/MessageList.tsx`:
```tsx
import { useEffect, useRef } from "react";
import type { Message } from "../types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: Message[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div ref={ref} className="flex-1 overflow-y-auto px-page py-block-lg flex flex-col gap-3">
      {messages.length === 0 && (
        <div className="m-auto text-center text-ink-secondary text-body2">
          您好，我是 Tevau AI 客服。
          <br />您可以描述遇到的问题，我会查证后给出答复。
        </div>
      )}
      {messages.map((m, i) => <MessageBubble key={i} m={m} />)}
    </div>
  );
}
```

`web/src/components/InputBox.tsx`:
```tsx
import { useState, type KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "./ui/button";

export function InputBox({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [v, setV] = useState("");

  function submit() {
    const text = v.trim();
    if (text && !disabled) { onSend(text); setV(""); }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  }

  return (
    <div className="border-t border-line bg-surface-card px-page py-block-sm safe-bottom">
      <div className="focus-glow flex items-end gap-2 rounded bg-white border border-line transition-all duration-250 px-3 py-2">
        <textarea
          value={v}
          rows={1}
          placeholder="描述你的问题…"
          onChange={e => setV(e.target.value)}
          onKeyDown={onKey}
          className="flex-1 resize-none bg-transparent text-body1 placeholder:text-ink-secondary outline-none max-h-32"
        />
        <Button
          size="icon"
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="h-9 w-9 rounded"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
```

`web/src/components/ChatWindow.tsx`:
```tsx
import { useChat } from "../hooks/useChat";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { MessageList } from "./MessageList";
import { InputBox } from "./InputBox";
import { HandoffButton } from "./HandoffButton";

export function ChatWindow() {
  const { messages, sending, send, requestHandoff, stop } = useChat();
  const inset = useKeyboardInset();

  return (
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-page-gradient"
      style={{ paddingBottom: inset }}
    >
      <header className="safe-top sticky top-0 z-10 flex items-center px-page py-3 bg-surface-card border-b border-line">
        <div className="h-7 w-7 rounded bg-brand grid place-items-center mr-2">
          <span className="text-ink-primary text-body0 font-bold">T</span>
        </div>
        <div className="flex-1">
          <div className="text-sh3 text-ink-primary">Tevau AI 客服</div>
          <div className="text-footnote text-ink-secondary">由 AI 驱动 · 复杂问题转人工</div>
        </div>
        {sending && (
          <button onClick={stop} className="text-body2 text-ink-secondary px-2">
            停止生成
          </button>
        )}
      </header>
      <MessageList messages={messages} />
      <HandoffButton onClick={requestHandoff} disabled={sending} />
      <InputBox onSend={send} disabled={sending} />
    </div>
  );
}
```

`web/src/components/HandoffButton.tsx`（spec §13.7 + §11 line 551，MVP-1 兜底）:
```tsx
/**
 * "没解决？转人工 →" 按钮。MVP-1 不调 /request-human 端点（spec §13.7）——
 * 点击后由 useChat 发送固定 user message "我想转人工"，AI 通过 prompt 识别意图自动建工单。
 */
export function HandoffButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <div className="px-page py-2 border-t border-line bg-surface-card">
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full text-body2 text-ink-secondary py-2 rounded border border-line hover:bg-surface-hover disabled:opacity-50"
      >
        没解决？转人工 →
      </button>
    </div>
  );
}
```

`web/src/App.tsx`:
```tsx
import { ChatWindow } from "./components/ChatWindow";
import "./styles/globals.css";

export default function App() {
  return <ChatWindow />;
}
```

`web/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>
);
```

- [ ] **Step 9: 写 `web/tests/useChat.test.ts`**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

vi.mock("../src/api/chat", () => ({
  streamChat: async function* () {
    yield { type: "conversation", conversation_id: 42 };
    yield { type: "text", text: "你" };
    yield { type: "text", text: "好" };
    yield { type: "done" };
  },
}));

import { useChat } from "../src/hooks/useChat";

describe("useChat", () => {
  it("accumulates text events into the latest assistant bubble", async () => {
    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.send("hi");
    });
    await waitFor(() => {
      const last = result.current.messages.at(-1)!;
      expect(last.role).toBe("assistant");
      expect((last as any).content).toBe("你好");
    });
  });
});
```

- [ ] **Step 10: 写 `web/tests/ChatWindow.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../src/api/chat", () => ({
  streamChat: async function* () {
    yield { type: "conversation", conversation_id: 1 };
    yield { type: "text", text: "已收到。" };
    yield { type: "done" };
  },
}));

import { ChatWindow } from "../src/components/ChatWindow";

describe("ChatWindow", () => {
  it("sends a message and shows assistant reply", async () => {
    render(<ChatWindow />);
    const input = screen.getByPlaceholderText("描述你的问题…");
    fireEvent.change(input, { target: { value: "hi" } });
    fireEvent.click(screen.getByText("发送"));
    await waitFor(() => expect(screen.getByText("已收到。")).toBeTruthy());
  });
});
```

- [ ] **Step 11: 跑测试**

```bash
cd web && pnpm install && pnpm test --run
```
Expected: 2 passed

- [ ] **Step 12: Commit**

```bash
git add web
git commit -m "feat(mvp-1): React 前端骨架（Vite+TS）+ Tailwind 接 APP 设计系统 + shadcn/ui + markdown 渲染 + SSE 流式对话"
```

---
