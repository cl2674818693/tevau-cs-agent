# Task 11: Prompt 管理面板（admin）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/api/admin_prompts.py`
- Create: `web/src/routes/admin/PromptsRoute.tsx`

简单版：
- `GET /admin/api/v1/prompts/versions` → 列所有版本 + 当前 rollout
- `POST /admin/api/v1/prompts/rollout` → 改 rollout 配置（admin role 权限）
- 前端面板：可视化展示版本 + 调比例 + 点 "save" 触发热加载

- [ ] Commit:
```bash
git commit -m "feat(mvp-3): Prompt 管理面板（admin 调整版本灰度比例）"
```

---
