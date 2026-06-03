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
_ID_CARD_RE = re.compile(r"\b\d{17}[\dXx]\b")  # 中国大陆 18 位身份证（含 X 结尾）
# 卡号：连续 13-19 位，或带空格/连字符分隔的 4-4-4-(1~4) 形式
_CARD_RE = re.compile(r"\b(?:\d{4}[ -]){3}\d{1,4}\b|\b\d{13,19}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_RULE_NAME_RE = re.compile(r"\bR-\d{2,4}\b")


# 内部上游供应商品牌名 → 通用占位。BU/C 端用户不应通过 AI 回复或 search_code/read_file
# 工具返回内容反推 Tevau 对接的真实三方（合规与商业秘密）。Alipay 是面向 C 端用户的支付
# 品牌，不在脱敏范围（C 端常需直接答"能否用支付宝充值"）。
# CamelCase 类名（ReapXxx）保留类名结构、只换品牌部分（→ UpstreamXxx），AI 仍能据此定位源码；
# 独立单词（叙述性文字中的 "Reap"）替换为中文占位标签。
_BRAND_TO_CAMEL = {
    "Reap": "Upstream",
    "reap": "upstream",
    "SX": "Upstream",
    "sx": "upstream",
    "Sumsub": "KycVendor",
    "sumsub": "kycvendor",
    "Jumio": "KycVendor",
    "jumio": "kycvendor",
    "Antom": "PayChannel",
    "antom": "paychannel",
}
_BRAND_TO_LABEL = {
    "Reap": "[上游通道]", "reap": "[上游通道]", "REAP": "[上游通道]",
    "SX": "[上游通道]",  # 注意：小写独立词 sx 不脱（易与 tx/rx/sx 通讯简写冲突），只脱大写 SX
    "Sumsub": "[KYC服务商]", "sumsub": "[KYC服务商]", "SUMSUB": "[KYC服务商]",
    "Jumio": "[KYC服务商]", "jumio": "[KYC服务商]", "JUMIO": "[KYC服务商]",
    "Antom": "[支付通道]", "antom": "[支付通道]", "ANTOM": "[支付通道]",
}
# CamelCase 前缀：品牌 + 大写字母开头的类名后缀 → 换品牌部分保留后缀
_VENDOR_CAMEL_RE = re.compile(r"\b(Reap|SX|Sumsub|Jumio|Antom)(?=[A-Z])")
# snake_case / package 路径：品牌 + 下划线/点 → 换品牌部分保留后缀
_VENDOR_LOWER_RE = re.compile(r"\b(reap|sx|sumsub|jumio|antom)(?=[_.])")
# 独立单词（所有 case 变体）→ 中文占位。SX 仅大写形式参与匹配，规避 tx/rx/sx 等通讯简写误伤
_VENDOR_WORD_RE = re.compile(
    r"\b(Reap|reap|REAP|SX|Sumsub|sumsub|SUMSUB|Jumio|jumio|JUMIO|Antom|antom|ANTOM)\b"
)


def mask_vendor_names(text: str) -> str:
    """脱敏内部上游供应商品牌名。三步：
    1. CamelCase 类名（ReapXxx → UpstreamXxx）保结构
    2. snake_case / package 路径（com.foo.reap.bar → com.foo.upstream.bar）保结构
    3. 剩下的独立词（叙述里的 "Reap 通道"）→ 中文占位标签 "[上游通道]"

    顺序重要：CamelCase / snake_case 优先消化掉品牌在标识符里的出现，最后剩下的才是
    独立单词，由 _VENDOR_WORD_RE 替换为占位。
    """
    if not text:
        return text
    text = _VENDOR_CAMEL_RE.sub(lambda m: _BRAND_TO_CAMEL[m[1]], text)
    text = _VENDOR_LOWER_RE.sub(lambda m: _BRAND_TO_CAMEL[m[1]], text)
    text = _VENDOR_WORD_RE.sub(lambda m: _BRAND_TO_LABEL[m[1]], text)
    return text


def scan_and_redact_text(text: str) -> str:
    text = _PHONE_RE.sub(lambda m: mask_phone(m.group()), text)
    text = _ID_CARD_RE.sub(lambda m: mask_id_card(m.group()), text)  # 先于卡号，保 X 结尾正确归类
    text = _CARD_RE.sub(lambda m: mask_card_no(m.group()), text)
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group()), text)
    text = _RULE_NAME_RE.sub("[风控规则]", text)
    text = mask_vendor_names(text)  # 兜底：AI 流出的最终文本里若仍残留品牌名再过一遍
    return text
