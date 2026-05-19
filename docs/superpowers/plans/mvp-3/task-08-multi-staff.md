# Task 8: 多客服协作（转工程师 + KPI）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `staff_conversations.py`：`/transfer-to/{role}` 端点
- Create: `src/ai_engine/api/staff_kpi.py`
- Create: 前端 `KpiRoute.tsx`

- [ ] **Step 1: 转工程师 endpoint**

```http
POST /staff/api/v1/conversations/{id}/transfer-to/{staff_id}
→ 当前 staff 释放 + 直接分给目标 staff_id
→ 推 SSE 事件给目标 staff（已分给你）
权限：agent 可转 engineer；engineer 可转任意 staff
```

- [ ] **Step 2: KPI 端点**

```http
GET /staff/api/v1/kpi?from=...&to=...
→ 返回：每客服的接管数 / 平均接管时长 / 释放回 AI 比例 / 用户满意度（来自 user_confirmed_resolved 比率）
```

- [ ] **Step 3: 前端 KpiRoute**：图表展示

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mvp-3): 多客服协作（转工程师 + KPI 看板）"
```

---
