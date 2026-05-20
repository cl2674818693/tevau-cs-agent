# Task 2: 数据脱敏 utils（工具层共用）

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `server/src/ai_engine/integrations/redact.py`
- Create: `server/tests/test_redact.py`

按 spec §5.4 实施工具层脱敏。

- [ ] **Step 1: 写 `server/tests/test_redact.py`**

```python
import pytest
from ai_engine.integrations.redact import (
    mask_phone, mask_id_card, mask_card_no, mask_email, scrub_dict, scan_and_redact_text,
)


def test_mask_phone():
    assert mask_phone("13812345678") == "138****78"
    assert mask_phone("12345") == "*****"  # 不够长直接全 *


def test_mask_id_card():
    assert mask_id_card("330106199001012345") == "33**************45"
    assert mask_id_card("X1234") == "*****"


def test_mask_card_no():
    assert mask_card_no("4938750672464590") == "4938 **** **** 4590"


def test_mask_email():
    assert mask_email("alice@example.com") == "al***@example.com"
    assert mask_email("a@x.com") == "*@x.com"


def test_scrub_dict_recursive():
    raw = {
        "user": {"phone": "13812345678", "email": "ab@x.com"},
        "card": {"card_no": "4938750672464590", "lock_reason": "R-217 风控误判"},
    }
    out = scrub_dict(raw, rules={
        "phone": mask_phone, "email": mask_email, "card_no": mask_card_no,
        "lock_reason": lambda s: "风控规则命中" if s else s,
    })
    assert out["user"]["phone"] == "138****78"
    assert out["user"]["email"] == "ab***@x.com"
    assert out["card"]["card_no"] == "4938 **** **** 4590"
    assert "R-217" not in out["card"]["lock_reason"]


def test_scan_text_redacts_loose_pii():
    """LLM 输出兜底扫描：哪怕工具忘了脱敏，文本输出再过一遍。"""
    txt = "用户手机 13812345678 卡号 4938750672464590 邮箱 alice@x.com"
    out = scan_and_redact_text(txt)
    assert "13812345678" not in out
    assert "4938750672464590" not in out
    assert "alice@x.com" not in out
```

- [ ] **Step 2: 写 `server/src/ai_engine/integrations/redact.py`**

```python
import re
from collections.abc import Callable
from typing import Any


def mask_phone(s: str | None) -> str:
    if not s:
        return ""
    if len(s) < 7:
        return "*" * len(s)
    return f"{s[:3]}****{s[-2:]}"  # spec §5.4 示例 138****12：固定 4 星（与测试一致，不随长度变）


def mask_id_card(s: str | None) -> str:
    if not s:
        return ""
    if len(s) < 6:
        return "*" * len(s)
    return f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"


def mask_card_no(s: str | None) -> str:
    if not s:
        return ""
    d = re.sub(r"\D", "", s)
    if len(d) < 10:
        return "*" * len(d)
    return f"{d[:4]} **** **** {d[-4:]}"


def mask_email(s: str | None) -> str:
    if not s:
        return ""
    if "@" not in s:
        return "*" * len(s)
    local, domain = s.split("@", 1)
    if len(local) <= 1:
        return f"{'*' * len(local)}@{domain}"
    return f"{local[:2]}***@{domain}"  # spec §5.4: 本地保留 2 字符 + ***（"ab"→"ab***"）


def scrub_dict(d: Any, rules: dict[str, Callable[[str], str]]) -> Any:
    """按字段名规则递归脱敏 dict / list。"""
    if isinstance(d, dict):
        return {k: rules[k](v) if k in rules and isinstance(v, str) else scrub_dict(v, rules)
                for k, v in d.items()}
    if isinstance(d, list):
        return [scrub_dict(x, rules) for x in d]
    return d


# LLM 输出兜底扫描：正则识别可能的 PII 并替换
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_CARD_RE = re.compile(r"\b\d{13,19}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RULE_NAME_RE = re.compile(r"\bR-\d{2,4}\b")


def scan_and_redact_text(text: str) -> str:
    text = _PHONE_RE.sub(lambda m: mask_phone(m.group()), text)
    text = _CARD_RE.sub(lambda m: mask_card_no(m.group()), text)
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group()), text)
    text = _RULE_NAME_RE.sub("[风控规则]", text)
    return text
```

- [ ] **Step 3: 跑测试**

```bash
pytest tests/test_redact.py -v
```
Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add server/src/ai_engine/integrations/redact.py server/tests/test_redact.py
git commit -m "feat(mvp-2): 数据脱敏 utils + LLM 输出兜底正则扫描（spec §5.4）"
```

---
