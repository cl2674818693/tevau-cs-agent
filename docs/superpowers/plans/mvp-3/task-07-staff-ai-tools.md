# Task 7: 客服调 AI 工具（staff 端代查接口）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `staff_conversations.py`：`/ai-tools/{tool_name}` 端点
- Modify: 前端：`AiToolsPanel.tsx`

让客服在工作台**让 AI 代查**（结果只显示给客服，不发用户）。

- [ ] **Step 1: endpoint**

```http
POST /staff/api/v1/conversations/{id}/ai-tools/{tool_name}
body: { params: {...} }
→ 经 tool_router.dispatch 调，强制以该会话的 subject_id 作为身份（不能跨用户）
→ 返回工具调用结果（脱敏 + engineer role 可解锁部分脱敏，见 §13.3）
```

权限：仅 senior + engineer 可用。

- [ ] **Step 2: 前端**

工作台右侧"上下文面板"里挂常用工具（query_user / query_card / search_code），点击带参数运行。结果显示在面板，**不进对话流**。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(mvp-3): 客服在工作台代查 AI 工具（结果仅客服可见）"
```

---
