# Task 14: 端到端 MVP-3 验收

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `tests/test_e2e_mvp3.py`

验收剧本：

1. **事项中心真接全链路**：AI 建工单 → 真事项中心收到 + 返回 internal_ticket_id → 事项中心模拟 assigned 回调 → 用户对话流 SSE 收到状态变更
2. **HMAC 双 key 轮换不停服**：用 PREVIOUS key 签的回调仍能通过验签
3. **self-check 触发**：mock LLM 第二次返回明显改写过的文本，断言最终流给用户的是修订版
4. **token 超额拒服**：连发 N 次让 token 总量超阈值 → 下次 chat 拿到"额度用完"系统消息
5. **ai_draft 模式**：客服切到 ai_draft → 用户问 → 客服侧 SSE 收到 draft_ready → approve 后用户对话流才收到 → reject + rewrite 后收到客服改写版
6. **客服转工程师**：agent 接管 → 转给 engineer → engineer 侧收到分派事件
7. **/metrics 暴露所有关键指标**

- [ ] **Step 1: 写测试**
- [ ] **Step 2: 全套测试通过**
- [ ] **Step 3: Commit**

```bash
git commit -m "test(mvp-3): 端到端验收（事项中心+self-check+治理+客服 C 方案+可观测）"
```

---
