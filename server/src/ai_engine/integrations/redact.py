import re
from collections.abc import Callable
from typing import Any


def mask_phone(s: str | None) -> str:
    if not s:
        return ""
    if len(s) < 7:
        return "*" * len(s)
    return f"{s[:3]}****{s[-2:]}"  # spec §5.4: 保留前 3 + 后 2


def mask_id_card(s: str | None) -> str:
    if not s:
        return ""
    if len(s) < 6:
        return "*" * len(s)
    return f"{s[:2]}{'*' * (len(s) - 4)}{s[-2:]}"  # spec §5.4: 保留前 2 + 后 2


def mask_card_no(s: str | None) -> str:
    if not s:
        return ""
    d = re.sub(r"\D", "", s)
    if len(d) < 10:
        return "*" * len(d)
    return f"{d[:4]} **** **** {d[-4:]}"  # spec §5.4: 保留前 4 + 后 4


def mask_email(s: str | None) -> str:
    if not s:
        return ""
    if "@" not in s:
        return "*" * len(s)
    local, domain = s.split("@", 1)
    if len(local) <= 1:
        return f"{'*' * len(local)}@{domain}"
    return f"{local[:2]}***@{domain}"  # spec §5.4: 本地部分保留 2 字符 + ***


def scrub_dict(d: Any, rules: dict[str, Callable[[str], str]]) -> Any:
    """按字段名规则递归脱敏 dict / list。"""
    if isinstance(d, dict):
        return {
            k: rules[k](v) if k in rules and isinstance(v, str) else scrub_dict(v, rules)
            for k, v in d.items()
        }
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
