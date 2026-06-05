"""B-P2-5: 用户输入文本清洗。

入口（chat message / staff send_message / ai_draft reject rewrite）必须先经此函数清洗，
再做长度校验与入库。原因：
- NULL 字节会破坏部分 DB driver 的 string 处理（PG 直接拒，MySQL 截断）。
- BOM / 零宽字符（U+200B/200C/200D/200E/200F/2060/FEFF）在 UI 不可见，用户能用它绕过
  "空消息"校验造无意义 LLM 调用；也常见于 phishing / homograph 攻击。
- 其他 C0 控制字符（0x00-0x1F 除 \\t/\\n/\\r 外）+ DEL（0x7F）在日志和审计存储中会
  造成显示错乱、转义不闭合等问题。
"""

# 显式删除的不可见 Unicode（除常规空白外）。源码本身不能含字面 NULL byte，全部用 escape。
_INVISIBLE_CODEPOINTS = frozenset(
    [
        0x0000,  # NULL
        0x200B,  # ZERO WIDTH SPACE
        0x200C,  # ZERO WIDTH NON-JOINER
        0x200D,  # ZERO WIDTH JOINER
        0x200E,  # LEFT-TO-RIGHT MARK
        0x200F,  # RIGHT-TO-LEFT MARK
        0x2060,  # WORD JOINER
        0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
    ]
)


def sanitize_user_text(s: str) -> str:
    """删除 NULL / BOM / 零宽字符 + 其他 C0 控制字符（保留 \\t \\n \\r）。

    返回的字符串可能比输入短（甚至变空）。上层应当在 sanitize **之后** 跑空校验，
    否则全是零宽字符的输入会被当成合法输入并送进 LLM/落库。
    """
    if not s:
        return s
    out_chars: list[str] = []
    for c in s:
        cp = ord(c)
        if cp in _INVISIBLE_CODEPOINTS:
            continue
        # 保留常见空白；其他 C0（0x01-0x1F）和 DEL（0x7F）丢弃
        if c in "\t\n\r" or (0x20 <= cp <= 0x7E) or cp >= 0x80:
            out_chars.append(c)
    return "".join(out_chars)
