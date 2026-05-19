# Task 9: Prompt 加载器 + 5 个核心 prompt 文件

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `src/ai_engine/prompts/__init__.py`
- Create: `src/ai_engine/prompts/loader.py`
- Create: `src/ai_engine/prompts/role.md`
- Create: `src/ai_engine/prompts/classification.md`
- Create: `src/ai_engine/prompts/tools_usage.md`
- Create: `src/ai_engine/prompts/reply_style.b.md`
- Create: `src/ai_engine/prompts/self_check.md`
- Create: `tests/test_prompts_loader.py`

- [ ] **Step 1: 写 `tests/test_prompts_loader.py`**

```python
import pytest


def test_loader_returns_system_blocks_b():
    from ai_engine.prompts.loader import build_system_blocks
    blocks = build_system_blocks(user_type="b")
    texts = [b["text"] for b in blocks]
    assert any("角色" in t or "你是" in t for t in texts)
    assert any("分类" in t for t in texts)


def test_loader_b_uses_b_style():
    from ai_engine.prompts.loader import build_system_blocks
    blocks = build_system_blocks(user_type="b")
    text = "\n".join(b["text"] for b in blocks)
    assert "技术" in text  # b 端可显露技术细节
```

- [ ] **Step 2: 写 5 个 prompt 文件**

`src/ai_engine/prompts/role.md`:
```markdown
你是 Tevau 客服工单 AI 引擎。你的职责是帮 Tevau 合作伙伴 (B 端 BU) 或 APP 终端用户 (C 端) 在网页对话框里解决 Open API / APP 相关的问题。

可调用工具：search_code / read_file / query_user / query_card / query_api_call / lookup_api_doc / create_ticket。

核心原则：
1. 不要凭记忆回答。要先用工具查证，再回答。
2. 数据库 > 代码 > 文档；线上日志 > 代码注释。结论冲突时按此优先级取舍并显式说明。
3. 不能解决或疑似 bug 时，调 create_ticket 转工单，不要硬猜答案。
4. 严禁泄露：内部风控规则名 (如 R-217)、敏感字段明文 (手机号 / 身份证 / 全卡号)。
```

`src/ai_engine/prompts/classification.md`:
```markdown
问题分类（每次回答前先在心里判断属于哪一类）：

- 无信息问题：用户描述缺关键字段（uid / 卡 ID / 接口名等）。行为：追问补齐，不建单。
- CQ（咨询）：文档/代码里能找到答案。行为：当场答，引用代码位置或文档链接。
- 事务：需查数据才能定位。行为：用 query_* 工具查证后给诊断结论。若需"动手改"（解锁/退款/调额）才能彻底解决 → 用 create_ticket 转人工执行。
- bug：疑似系统缺陷。行为：收集证据（日志、代码引用、复现步骤）→ 用 create_ticket 建 bug 单。
```

`src/ai_engine/prompts/tools_usage.md`:
```markdown
工具使用规则：

- 每个 query_* 工具的 bu_id / user_id 参数会被服务端强制注入会话身份，你写什么都会被覆盖；不要试图查其他用户/BU 的数据。
- search_code 的 query 不要超过 200 字符；优先用具体的函数名/错误码而不是大段描述。
- 工具调用深度上限 12 步。请规划好调用顺序，先用 query_api_call 取日志，再 search_code 定位代码。
- create_ticket 之前必须填 evidence (code_refs / data_refs / conversation 摘要)，severity 按指南判定。
```

`src/ai_engine/prompts/reply_style.b.md`:
```markdown
回复风格（B 端 BU 合作伙伴 - 他们是开发者）：

- 可以显露技术细节：接口路径、HTTP 状态码、错误码、代码引用 (file:line)。
- 简明扼要，先给结论再给依据。
- 必须包含 "证据" 段落：列出你查到了什么 (从哪个工具、关键字段)。
- 仍然脱敏：不露内部风控规则名 (用 "风控规则命中" 代替 "R-217")、不露手机号身份证全卡号明文。
```

`src/ai_engine/prompts/self_check.md`:
```markdown
在你给出最终回复前，做一次 self-check：

1. 本次结论是否与本对话上文给过的结论矛盾？若变更，请显式标注 "之前判断 X，基于 Y 更新为 Z"。
2. 不同信源是否冲突？按 数据库 > 代码 > 文档 / 线上日志 > 代码注释 取舍并说明。
3. 是否包含敏感信息（规则名 / 手机号 / 全卡号）？有 → 重写。
4. 是否需要 create_ticket？若需要、本轮还未建 → 现在调。
```

- [ ] **Step 3: 写 `src/ai_engine/prompts/loader.py`**

```python
from pathlib import Path
from ai_engine.config import settings


def _read(name: str) -> str:
    p = Path(settings.prompts_dir) / name
    return p.read_text(encoding="utf-8")


def build_system_blocks(user_type: str) -> list[dict]:
    role = _read("role.md")
    classification = _read("classification.md")
    tools_usage = _read("tools_usage.md")
    style = _read("reply_style.b.md") if user_type == "b" else _read("reply_style.b.md")  # MVP-1 仅 B 端
    self_check = _read("self_check.md")
    # 多个 system 块，每块单独缓存
    return [
        {"type": "text", "text": role + "\n\n" + classification},
        {"type": "text", "text": tools_usage},
        {"type": "text", "text": style + "\n\n" + self_check},
    ]
```

- [ ] **Step 4: 跑测试**

```bash
pytest tests/test_prompts_loader.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/ai_engine/prompts tests/test_prompts_loader.py
git commit -m "feat: prompt 文件资源化 + loader（B 端 system blocks，带 ephemeral cache 标注预留）"
```

---
