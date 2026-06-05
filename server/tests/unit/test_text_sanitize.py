"""B-P2-5: 用户输入文本清洗 —— 去除 NULL 字节 / BOM / 零宽字符 / 控制字符。

这些字符在 UI 上不可见但能：
- 绕过"空消息"校验（U+200B U+200C 看起来像空，trim 不去掉）
- 在日志/数据库 content 列造成显示错乱（NULL 字节 / BOM）
- 用于 Unicode-based phishing / homograph attack
"""

from ai_engine.utils.text_sanitize import sanitize_user_text


class TestSanitizeUserText:
    def test_removes_null_byte(self) -> None:
        assert sanitize_user_text("hello\x00world") == "helloworld"

    def test_removes_bom(self) -> None:
        assert sanitize_user_text("﻿hi") == "hi"

    def test_removes_zero_width_space(self) -> None:
        assert sanitize_user_text("a​b‌c‍d") == "abcd"

    def test_removes_word_joiner(self) -> None:
        assert sanitize_user_text("a⁠b") == "ab"

    def test_removes_c0_control_chars_but_keeps_whitespace(self) -> None:
        """\\t \\n \\r 是常见空白要保留；其他 0x00-0x1F + 0x7F 删除。"""
        assert sanitize_user_text("a\tb\nc\rd\x01e\x7ff") == "a\tb\nc\rdef"

    def test_preserves_emoji_and_4byte_unicode(self) -> None:
        """4 字节 UTF-8 emoji 必须保留，不能被误删。"""
        s = "你好 \U0001f44d \U0001f389 \U0001f31f"
        assert sanitize_user_text(s) == s

    def test_preserves_normal_text(self) -> None:
        s = "Hello, world! 123 - the quick brown fox."
        assert sanitize_user_text(s) == s

    def test_all_invisible_yields_empty(self) -> None:
        """全是不可见字符 → 清洗后变空（让上层"空消息"校验生效）。"""
        assert sanitize_user_text("​‌﻿\x00") == ""

    def test_empty_input_returns_empty(self) -> None:
        assert sanitize_user_text("") == ""
