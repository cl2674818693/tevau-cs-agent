# Task 6: 客服旁观模式（不接管，但订阅会话）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `staff_conversations.py`：spectate 端点
- Modify: 前端：`SpectateConversation.tsx`
- Create: `tests/test_spectate.py`

- [ ] **Step 1: spectate 不改 mode**，仅是客服侧加一个订阅项

```http
GET /staff/api/v1/conversations/{id}/spectate-stream
→ SSE，订阅该会话所有事件（user_message / assistant_text / tool_call / mode_changed）
权限：staff role ∈ {senior, engineer} 才能旁观（agent 只能看自己接管的）
```

- [ ] **Step 2: 前端**

工作台列表加"旁观"按钮（仅 senior+ 可见），进入只读视图，能看 AI 在做什么但不发消息。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(mvp-3): 客服旁观模式（senior/engineer 不接管观察 AI 处理）"
```

---
