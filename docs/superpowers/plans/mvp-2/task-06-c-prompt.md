# Task 6: C 端回复风格 prompt + loader 切换

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/prompts/reply_style.c.md`
- Modify: `src/ai_engine/prompts/loader.py`
- Create: `tests/test_prompts_c_style.py`

- [ ] **Step 1: 写 `src/ai_engine/prompts/reply_style.c.md`**

```markdown
回复风格（C 端 APP 终端用户 — 不是开发者）：

- **大白话**，不显露代码、不显露接口路径、不显露内部错误码、不显露数据库表名/字段名
- 最多说"系统记录到您 X 时间做了 Y 操作，结果是 Z"
- 用户问题往往是"我的卡为啥被锁"/"转账失败"/"按钮点了没反应" —— 按 §6.2 三层下钻（前端代码 → 后端代码 → 用户数据），但最终用用户能听懂的话翻译
- 引用代码位置只在你自己心里用作判断依据，**绝不输出 `file:line` 给用户**
- 不要让用户感到被技术细节淹没；如果需要技术介入，说"我已帮您创建工单，工程师会跟进"
- 涉及金额、卡片、个人信息时尤其谨慎；任何敏感字段（手机号 / 身份证 / 全卡号）严禁输出原文
- 内部风控规则名（如 R-217）—— **完全不露**，只翻译为业务原因（如"系统判断该操作存在风险"）
```

- [ ] **Step 2: 修改 `src/ai_engine/prompts/loader.py`**

```python
def build_system_blocks(user_type: str) -> list[dict]:
    role = _read("role.md")
    classification = _read("classification.md")
    tools_usage = _read("tools_usage.md")
    style = _read("reply_style.c.md") if user_type == "c" else _read("reply_style.b.md")
    self_check = _read("self_check.md")
    return [
        {"type": "text", "text": role + "\n\n" + classification},
        {"type": "text", "text": tools_usage},
        {"type": "text", "text": style + "\n\n" + self_check},
    ]
```

- [ ] **Step 3: 写 `tests/test_prompts_c_style.py`**

```python
def test_loader_c_returns_c_style():
    from ai_engine.prompts.loader import build_system_blocks
    blocks = build_system_blocks(user_type="c")
    text = "\n".join(b["text"] for b in blocks)
    assert "大白话" in text
    assert "file:line" in text  # 显式禁止
    assert "R-217" in text       # 显式禁止规则名
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_prompts_c_style.py tests/test_prompts_loader.py -v
```
Expected: 全部 passed

- [ ] **Step 5: Commit**

```bash
git add src/ai_engine/prompts/reply_style.c.md src/ai_engine/prompts/loader.py tests/test_prompts_c_style.py
git commit -m "feat(mvp-2): C 端语言化回复风格 prompt + loader 按 user_type 切换"
```

---
