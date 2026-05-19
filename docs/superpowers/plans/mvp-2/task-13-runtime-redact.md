# Task 13: LLM 输出兜底脱敏（runtime 流式输出过滤）

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `src/ai_engine/agent/runtime.py`
- Create: `tests/test_runtime_redact.py`

- [ ] **Step 1: 修改 runtime**

在 `runtime.run_turn` yield `{"type": "text", ...}` 前过一遍 `scan_and_redact_text`：

```python
from ai_engine.integrations.redact import scan_and_redact_text

# ... 在 yield 文本块的地方：
yield {"type": "text", "text": scan_and_redact_text(b["text"])}
```

- [ ] **Step 2: 写 `tests/test_runtime_redact.py`**

(测试代码：用 mock Anthropic 返回包含手机号/卡号/规则名的文本，断言 yield 出来的是脱敏后版本)

- [ ] **Step 3: Commit**

```bash
git add src/ai_engine/agent/runtime.py tests/test_runtime_redact.py
git commit -m "feat(mvp-2): LLM 输出兜底脱敏（runtime 流式过滤手机/卡号/邮箱/规则名）"
```

---
