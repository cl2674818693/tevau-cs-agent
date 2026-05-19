# Task 15: 客服工作台前端 SPA（B 方案最小版）

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `web/src/routes/staff/StaffLoginRoute.tsx`
- Create: `web/src/routes/staff/ConversationsListRoute.tsx`
- Create: `web/src/routes/staff/ConversationDetailRoute.tsx`
- Create: `web/src/hooks/useStaffSession.ts`
- Create: `web/src/api/staff.ts`
- Modify: `web/src/App.tsx`（加 /staff/* 路由）

- [ ] **Step 1: 写 `web/src/hooks/useStaffSession.ts`**

```ts
import { useState } from "react";

const KEY = "staff_jwt";

export function useStaffSession() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));
  function login(t: string) { localStorage.setItem(KEY, t); setToken(t); }
  function logout() { localStorage.removeItem(KEY); setToken(null); }
  return { token, login, logout };
}
```

- [ ] **Step 2: 写 `web/src/api/staff.ts`**

封装 staff 侧 API（list / take / release / send / SSE stream），所有调用带 `Authorization: Bearer <jwt>`。

- [ ] **Step 3: 写三个 Route 组件**

`StaffLoginRoute`: 表单 → POST /staff/api/v1/auth/login → 存 jwt → nav 到列表  
`ConversationsListRoute`: 拉 /staff/api/v1/conversations，按 mode 过滤，点击进详情  
`ConversationDetailRoute`: 加载该会话历史 + 订阅 SSE stream + 接管/释放/发消息 UI

- [ ] **Step 4: App.tsx 加路由**

```tsx
<Route path="/staff/login" element={<StaffLoginRoute />} />
<Route path="/staff/conversations" element={<ConversationsListRoute />} />
<Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat(mvp-2): 客服工作台 SPA v1（登录 / 列表 / 详情 / 接管+释放+收发）"
```

---
