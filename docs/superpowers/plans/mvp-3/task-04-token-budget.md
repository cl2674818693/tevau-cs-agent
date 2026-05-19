# Task 4: 成本治理硬阈值（单 BU/单 user 日 token 上限）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/governance/token_budget.py`
- Modify: 持久层加 `daily_token_usage` 表
- Modify: `runtime.py`（每轮 LLM 调用后扣减）
- Create: `tests/test_token_budget.py`

- [ ] **Step 1: 新表**

```sql
CREATE TABLE IF NOT EXISTS daily_token_usage (
    subject_id TEXT NOT NULL,           -- bu_id 或 user_id
    user_type TEXT NOT NULL,
    date TEXT NOT NULL,                 -- YYYY-MM-DD
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject_id, user_type, date)
);
```

- [ ] **Step 2: 写 `token_budget.py`**

```python
DEFAULT_DAILY_LIMIT_TOKENS = 500_000  # 调整时通过配置

async def check_and_record(user_type, subject_id, input_tok, output_tok) -> tuple[bool, dict]:
    """返回 (allowed, info)，info 含已用 / 上限 / 剩余。"""
    today = date.today().isoformat()
    # 查当日使用量
    used = await _get_used(subject_id, user_type, today)
    if used["input_tokens"] + used["output_tokens"] >= DEFAULT_DAILY_LIMIT_TOKENS:
        return False, {"used": used, "limit": DEFAULT_DAILY_LIMIT_TOKENS}
    # 80% 提醒
    pct = (used["input_tokens"] + used["output_tokens"]) / DEFAULT_DAILY_LIMIT_TOKENS
    await _record(subject_id, user_type, today, input_tok, output_tok)
    return True, {"used": used, "limit": DEFAULT_DAILY_LIMIT_TOKENS,
                  "warn": pct > 0.8}
```

- [ ] **Step 3: runtime 在每轮 LLM 返回后调用 record；超额时下次 run_turn 拒服**

```python
allowed, info = await check_and_record(user_type, subject_id, resp.usage.input_tokens, resp.usage.output_tokens)
if not allowed:
    yield {"type": "system", "text": "您今日的 AI 服务额度已用完，请明日再试，或点'转人工'。"}
    return
if info.get("warn"):
    yield {"type": "system", "text": "您今日 AI 服务额度已用 80%。"}
```

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(mvp-3): 单 BU/单 user 单日 token 硬阈值（80% 提醒 + 100% 拒服）"
```

---
