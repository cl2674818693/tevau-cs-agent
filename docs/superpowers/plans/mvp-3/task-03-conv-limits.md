# Task 3: 会话长度治理（轮次 / token 上限 + 自动总结）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `server/src/ai_engine/governance/conversation_limits.py`
- Create: `server/src/ai_engine/agent/conversation_compactor.py`
- Modify: `runtime.py`
- Create: `server/tests/test_conversation_limits.py`

- [ ] **Step 1: 写 `conversation_limits.py`**

```python
MAX_TURNS = 20
MAX_INPUT_TOKENS = 100_000

async def should_compact(conv_id: int) -> bool:
    """检查该会话是否需要总结+开新会话。"""
    turns = await _count_turns(conv_id)
    tokens = await _estimate_tokens(conv_id)
    return turns >= MAX_TURNS or tokens >= MAX_INPUT_TOKENS
```

- [ ] **Step 2: 写 `conversation_compactor.py`**

```python
async def compact_conversation(conv_id: int) -> int:
    """用 Claude 把前 N-2 轮总结成一段，开新会话继承结论。返回新 conv_id。"""
    # 1. 拉历史消息
    # 2. 调 claude-haiku-4-5 做"提取关键诊断和待办"
    # 3. 新建 conversation，把总结作为 system 注入第一条
    # 4. 老会话标 archived
    # 5. 给用户对话流推 system 事件"会话过长，已为您开启新会话"
    ...
```

- [ ] **Step 3: runtime 入口检查**

```python
# run_turn 开头：
if await should_compact(conv_id):
    new_id = await compact_conversation(conv_id)
    yield {"type": "system", "text": f"会话过长，已开启新对话，conversation_id={new_id}"}
    conv_id = new_id  # 后续用新 id
```

- [ ] **Step 4: 测试 + Commit**

```bash
git commit -m "feat(mvp-3): 会话长度治理（≤20 轮 / ≤100K token + 自动总结+开新会话）"
```

---
