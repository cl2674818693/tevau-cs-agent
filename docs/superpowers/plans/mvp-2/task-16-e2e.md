# Task 16: 端到端 MVP-2 验收

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `tests/test_e2e_mvp2.py`

验收剧本：
1. **C 端 APP 用户问问题 → AI 用 C 端风格回答**：JWT 验签通过、prompt 切到 c style、回复不含 file:line / R-217 / 手机号原文
2. **C 端用户点"转人工" → 客服在工作台看到 → 接管 → 直接回话 → 用户看到客服气泡**
3. **B 端 BU 登录 → 问 card_bind 500 → AI 调真 MySQL query_api_call → 回复带 file:line（B 端风格）**
4. **B 端 user_id 越权 → 服务端拒绝 → AI 在回复里说"我没权限"**
5. **C 端用户点 TicketCard "未解决" → 反向 webhook → 工单 reopen → 事项中心 mock 收到 reopen 事件**

- [ ] **Step 1: 写 `tests/test_e2e_mvp2.py`**（覆盖以上 5 个验收剧本）

- [ ] **Step 2: 跑全套测试**

```bash
pytest -v
cd web && pnpm test
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e_mvp2.py
git commit -m "test(mvp-2): 端到端验收（C/B 端 + 客服接管 + 真 MySQL + 反向 webhook）"
```

---
