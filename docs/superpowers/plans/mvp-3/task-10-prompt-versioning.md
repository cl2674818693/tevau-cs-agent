# Task 10: Prompt 版本化 + 哈希分桶灰度

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `src/ai_engine/prompts/registry.py`
- Modify: `src/ai_engine/prompts/loader.py`
- 引入新目录：`prompts/v1.0.0/`、`prompts/v1.1.0/`...
- Create: `tests/test_prompt_registry.py`

- [ ] **Step 1: prompts 目录改为按版本组织**

```
src/ai_engine/prompts/
├── v1.0.0/        # MVP-1 起始版本
│   ├── role.md
│   ├── classification.md
│   └── ...
├── v1.1.0/        # MVP-2 + C 端风格
│   ├── role.md
│   ├── reply_style.c.md
│   └── ...
└── registry.yaml  # 版本声明 + 灰度配置
```

`registry.yaml`:
```yaml
versions:
  v1.0.0:
    model: claude-sonnet-4-6
    files: { role: v1.0.0/role.md, ... }
  v1.1.0:
    model: claude-sonnet-4-6
    files: { role: v1.1.0/role.md, ... }
default: v1.1.0
rollout:
  v1.1.0: 100   # 100% 灰度比例（按 user/bu_id 哈希分桶）
```

- [ ] **Step 2: 写 `registry.py`**

```python
def pick_version(subject_id: str) -> str:
    """按 subject_id 哈希分桶选 prompt 版本。"""
    cfg = _load_registry()
    h = int(hashlib.md5(subject_id.encode()).hexdigest(), 16) % 100
    cumulative = 0
    for v, pct in cfg["rollout"].items():
        cumulative += pct
        if h < cumulative:
            return v
    return cfg["default"]
```

- [ ] **Step 3: 修 loader 走 registry**

- [ ] **Step 4: 测试 + Commit**

```bash
git commit -m "feat(mvp-3): Prompt 版本化 + 按 subject_id 哈希分桶灰度"
```

---
