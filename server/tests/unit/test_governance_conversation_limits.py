"""Unit tests: governance.conversation_limits

被测对象：会话长度治理（轮次 + 输入 token 上限），超限触发 compactor。
mock 策略：直接 monkeypatch DAO 层 count_user_turns / sum_content_chars，
不实际触 DB，纯检查 should_compact 的判定逻辑。
"""

import pytest

from ai_engine.governance import conversation_limits as cl


def _patch_dao(monkeypatch, turns: int, chars: int) -> None:
    async def _turns(_id: int) -> int:
        return turns

    async def _chars(_id: int) -> int:
        return chars

    monkeypatch.setattr(cl, "count_user_turns", _turns)
    monkeypatch.setattr(cl, "sum_content_chars", _chars)


class TestEstimateTokensFromChars:
    """纯函数：粗估 token 数（1 token ≈ 4 字符）。"""

    @pytest.mark.parametrize(
        "chars, expected",
        [
            (0, 0),
            (1, 0),
            (3, 0),
            (4, 1),
            (7, 1),
            (8, 2),
            (100, 25),
            (10_000, 2_500),
            (400_000, 100_000),
        ],
    )
    def test_estimate_tokens_from_chars_known_values(self, chars: int, expected: int) -> None:
        assert cl.estimate_tokens_from_chars(chars) == expected


class TestShouldCompact:
    """should_compact 决策矩阵：轮次或 token 任一超阈值即 True，否则 False。"""

    async def test_returns_false_when_both_under_limit(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=5, chars=1000)
        assert await cl.should_compact(conv_id=1) is False

    async def test_returns_false_at_zero(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=0, chars=0)
        assert await cl.should_compact(conv_id=1) is False

    async def test_returns_true_when_turns_at_limit(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=cl.MAX_TURNS, chars=0)
        assert await cl.should_compact(conv_id=1) is True

    async def test_returns_true_when_turns_above_limit(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=cl.MAX_TURNS + 100, chars=0)
        assert await cl.should_compact(conv_id=1) is True

    async def test_returns_false_when_turns_just_below_limit(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=cl.MAX_TURNS - 1, chars=0)
        assert await cl.should_compact(conv_id=1) is False

    async def test_returns_true_when_tokens_at_limit(self, monkeypatch) -> None:
        # token 阈值 100_000；chars=400_000 → 100_000 tokens 正好等于
        _patch_dao(monkeypatch, turns=0, chars=cl.MAX_INPUT_TOKENS * 4)
        assert await cl.should_compact(conv_id=1) is True

    async def test_returns_true_when_tokens_above_limit(self, monkeypatch) -> None:
        _patch_dao(monkeypatch, turns=0, chars=(cl.MAX_INPUT_TOKENS + 1) * 4)
        assert await cl.should_compact(conv_id=1) is True

    async def test_returns_false_when_tokens_just_below_limit(self, monkeypatch) -> None:
        # 阈值 -1 → 99_999 tokens；99_999 * 4 = 399_996 chars
        _patch_dao(monkeypatch, turns=0, chars=(cl.MAX_INPUT_TOKENS - 1) * 4)
        assert await cl.should_compact(conv_id=1) is False

    async def test_returns_true_when_only_turns_exceed(self, monkeypatch) -> None:
        # 仅轮次超限，token 完全未达：任一即触发
        _patch_dao(monkeypatch, turns=cl.MAX_TURNS + 5, chars=100)
        assert await cl.should_compact(conv_id=1) is True

    async def test_returns_true_when_only_tokens_exceed(self, monkeypatch) -> None:
        # 仅 token 超限，轮次未达
        _patch_dao(monkeypatch, turns=3, chars=(cl.MAX_INPUT_TOKENS + 1) * 4)
        assert await cl.should_compact(conv_id=1) is True

    async def test_dao_failure_propagates(self, monkeypatch) -> None:
        """异常：DAO 抛错应直接传播，不静默吞掉（让上层决定 compactor 是否仍触发）。"""

        async def _boom(_id: int) -> int:
            raise RuntimeError("db down")

        monkeypatch.setattr(cl, "count_user_turns", _boom)
        with pytest.raises(RuntimeError, match="db down"):
            await cl.should_compact(conv_id=1)
