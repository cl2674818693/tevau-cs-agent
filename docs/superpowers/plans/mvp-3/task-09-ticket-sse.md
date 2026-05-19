# Task 9: 工单状态实时推前端（SSE 长连，替换 MVP-2 轮询）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `server/src/ai_engine/api/ticket_events_sse.py`
- Modify: 前端 `ChatRoute.tsx`：换轮询为 SSE

- [ ] **Step 1: 后端端点**

```http
GET /api/v1/conversations/{id}/ticket-events-stream
Auth: session cookie (B) 或 Bearer JWT (C)
→ SSE 长连，订阅该会话所有工单事件（assigned/in_progress/escalated/resolved/closed/reopen）
```

实现：复用 `_subscribers` 总线（MVP-2 Task 9 已建），事项中心回调入口 `/api/v1/tickets/{id}/events` 收到事件后 `_publish` 到该 conv 的 subscribers。

- [ ] **Step 2: 前端**

```tsx
// useTicketStream.ts
useEffect(() => {
  const sse = new EventSource(`/api/v1/conversations/${convId}/ticket-events-stream`);
  sse.addEventListener("assigned", e => ...);
  sse.addEventListener("resolved", e => ...);
  return () => sse.close();
}, [convId]);
```

- [ ] **Step 3: 删除 MVP-2 阶段的轮询代码**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mvp-3): 工单状态实时推前端（SSE 长连替换 MVP-2 轮询）"
```

---
