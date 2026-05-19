# Task 14: React 前端 —— 路由 + B 端登录页 + 三色气泡 + 转人工按钮

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `web/package.json`（加 react-router-dom）
- Modify: `web/src/App.tsx`
- Create: `web/src/routes/BuLoginRoute.tsx`
- Create: `web/src/routes/ChatRoute.tsx`
- Modify: `web/src/types.ts`（加 mode/user_type/human_agent message 类型）
- Modify: `web/src/hooks/useChat.ts`（处理 human_message 事件 + mode）
- Modify: `web/src/components/MessageBubble.tsx`（加 human_agent 样式）
- Modify: `web/src/components/TicketCard.tsx`（加"已解决/未解决"按钮 → 调 user-events）
- Create: `web/src/components/RequestHumanButton.tsx`
- Create: `web/src/hooks/useAppBridge.ts`（C 端 JS Bridge）

- [ ] **Step 1: 加路由依赖**

```bash
cd web && pnpm add react-router-dom
```

- [ ] **Step 2: 写 `web/src/App.tsx`（用 BrowserRouter）**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ChatRoute } from "./routes/ChatRoute";
import { BuLoginRoute } from "./routes/BuLoginRoute";
// staff 路由在 Task 15 加
import "./styles.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatRoute />} />
        <Route path="/bu/login" element={<BuLoginRoute />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: 写 `web/src/routes/BuLoginRoute.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function BuLoginRoute() {
  const [buId, setBuId] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const r = await fetch("/api/v1/auth/bu/login", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bu_id: buId.trim() }),
      });
      if (!r.ok) {
        const t = await r.text();
        setErr(t || "登录失败");
        return;
      }
      nav("/");
    } finally { setLoading(false); }
  }

  return (
    <div className="login-container">
      <h2>Tevau AI 客服</h2>
      <form onSubmit={submit}>
        <input value={buId} onChange={e => setBuId(e.target.value)}
               placeholder="主账户 ID（例如 BU00243780）" />
        <button type="submit" disabled={loading || !buId.trim()}>
          {loading ? "..." : "进入对话"}
        </button>
        {err && <div className="err">{err}</div>}
      </form>
    </div>
  );
}
```

- [ ] **Step 4: 改 `web/src/hooks/useChat.ts` 处理 human_message + mode**

```ts
// 在 streamChat 的循环里加：
} else if (ev.type === "human_message") {
  setMessages(prev => [...prev, { role: "human_agent", content: ev.content, staff_id: ev.staff_id }]);
} else if (ev.type === "system") {
  setMessages(prev => [...prev, { role: "system", content: ev.text }]);
} else if (ev.type === "mode_changed") {
  setMode(ev.mode);
}
```

- [ ] **Step 5: 改 `web/src/components/MessageBubble.tsx`**

加 human_agent 气泡（黄色背景 + "客服 XXX" 头像）和 system 气泡（居中浅色）。

- [ ] **Step 6: 写 `web/src/components/RequestHumanButton.tsx`**

```tsx
export function RequestHumanButton({ conversationId, onRequested }: { conversationId: number; onRequested: () => void }) {
  return (
    <button onClick={async () => {
      await fetch(`/api/v1/conversations/${conversationId}/request-human`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "用户请求人工" }),
      });
      onRequested();
    }}>转人工</button>
  );
}
```

挂在 `ChatRoute.tsx` 输入框附近。

- [ ] **Step 7: 改 `TicketCard.tsx` 加"已解决/未解决"按钮**

```tsx
<button onClick={() => fetch(`/api/v1/tickets/${externalId}/user-events`, {
  method: "POST", credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ event: "user_confirmed_resolved" }),
})}>已解决</button>
<button onClick={...}>未解决</button>
```

- [ ] **Step 8: 写 `useAppBridge.ts`（C 端 JS Bridge）**

```ts
import { useEffect, useState } from "react";

export function useAppBridge() {
  const [jwt, setJwt] = useState<string | null>(null);
  useEffect(() => {
    (window as any).aiEngineSetToken = (token: string) => setJwt(token);
    (window as any).aiEngineRequestToken?.();  // APP 实现这个回调来注入 jwt
  }, []);
  return jwt;
}
```

C 端入口在 `ChatRoute.tsx` 检测 `useAppBridge()` 拿到的 JWT，之后 fetch 加 `Authorization: Bearer <jwt>` header（不带 cookie）。

- [ ] **Step 9: 跑前端测试 + Commit**

```bash
cd web && pnpm test
git add web
git commit -m "feat(mvp-2): React 路由 + B 端登录页 + 三色气泡 + 转人工按钮 + C 端 JS Bridge"
```

---
