# Task 5: 客服 ai_draft 模式（草稿审核）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `server/src/ai_engine/api/chat.py`（mode=ai_draft 时 AI 输出不发用户、放到 staff 工作台）
- Modify: `server/src/ai_engine/api/staff_conversations.py`（add /ai-draft/{enable} / approve / reject）
- Modify: `web/src/routes/staff/...`
- Create: `server/tests/test_ai_draft.py`

- [ ] **Step 1: chat 端点逻辑**

```python
if mode == "ai_draft":
    # AI 生成回复但不流给用户；写入一个"待审"消息（role='ai_draft'）
    draft = await runtime.collect_full_response(...)
    await persistence.save_ai_draft(conv_id, draft)
    _publish(conv_id, {"type": "ai_draft_ready", "draft": draft})  # 给客服侧 SSE
    yield {"type": "system", "text": "客服正在 review 您的回答…"}
    return
```

- [ ] **Step 2: staff 端 endpoints**

```http
POST /staff/api/v1/conversations/{id}/ai-draft/enable  → 切到 ai_draft 模式
POST /staff/api/v1/conversations/{id}/ai-draft/disable → 切回 ai
POST /staff/api/v1/conversations/{id}/ai-draft/approve → 把 draft 当作 assistant 消息流给用户
POST /staff/api/v1/conversations/{id}/ai-draft/reject  → 客服改写后再发
  body: { rewrite: "客服重新写的回答" }
```

- [ ] **Step 3: 前端**

`AiDraftPanel.tsx`：显示 AI 草稿 + 两个按钮（发出 / 改写后发）+ 改写文本框。

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mvp-3): 客服 ai_draft 模式（AI 出草稿、客服 review/改写后发）"
```

---
