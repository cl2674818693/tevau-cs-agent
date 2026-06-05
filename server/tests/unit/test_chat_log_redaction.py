"""B-P2-2: chat 日志中 conversation_id 不应明文记录（防低权运维枚举 / 撞库）。

日志层用稳定 8 字符 hash 替代明文 conversation_id，既保留按会话排查问题的能力，
又不泄漏可枚举的连续整数 ID。
"""

from ai_engine.api.chat import _conv_id_log_repr


class TestConvIdLogRepr:
    def test_returns_8_char_hex(self) -> None:
        r = _conv_id_log_repr(42)
        assert len(r) == 8
        assert all(c in "0123456789abcdef" for c in r)

    def test_not_plain_integer(self) -> None:
        """脱敏后必须与原始整数字符串不同（防 hash 函数实现错误退化为 str(id)）。"""
        assert _conv_id_log_repr(42) != "42"
        assert _conv_id_log_repr(99999) != "99999"

    def test_deterministic(self) -> None:
        assert _conv_id_log_repr(42) == _conv_id_log_repr(42)

    def test_different_ids_yield_different_hashes(self) -> None:
        """正常情况下不同会话 ID 输出不同 hash（碰撞需 2^32 量级，单测够用）。"""
        assert _conv_id_log_repr(1) != _conv_id_log_repr(2)
