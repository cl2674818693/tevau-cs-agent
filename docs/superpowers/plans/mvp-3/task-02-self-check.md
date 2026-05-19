# Task 2: 多轮一致性 self-check 强制 inject

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

按 spec §8.3：agent 在 `stop_reason == "end_turn"` 后追加一轮 self-check 调用。

**Files:**
- Modify: `src/ai_engine/agent/runtime.py`
- Create: `tests/test_self_check.py`

- [ ] **Step 1: 改 runtime（核心改造）**

```python
# runtime.py 主循环末尾增加：
if resp.stop_reason == "end_turn" and not _self_check_done:
    # 第一轮的回复缓存住，不流给用户
    draft_text = "".join(b["text"] for b in assistant_blocks if b["type"] == "text")
    # 注入 self_check
    self_check_md = _read_prompt("self_check.md")
    messages.append({"role": "user", "content":
        f"在你给出上面这段最终回复之前，请按以下规则做一次审视：\n\n{self_check_md}\n\n"
        f"现给出修订后的回复（如无需修订则原样重复）。"})
    _self_check_done = True
    continue  # 再调一次 messages.create
```

- [ ] **Step 2: cost guard 不计 self-check 次数**（避免占工具调用深度）

- [ ] **Step 3: 测试用 mock：第一轮返回的 text 与 self-check 后返回的不同 → 流给用户的是 self-check 后版本**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mvp-3): self-check 强制 inject（end_turn 后追加一轮一致性审视）"
```

---
