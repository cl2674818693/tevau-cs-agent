"""Unit tests: agent.topic_classifier

被测对象：spec §6.4 第二层话题分类（haiku）。
mock 策略：monkeypatch `_ac.classify_topic`（async）—— 测试不打 anthropic。
"""

import pytest

from ai_engine.agent import topic_classifier as tc


def _patch_classify(monkeypatch, word: str | Exception) -> None:
    """伪造 _ac.classify_topic：返回固定字符串或抛指定异常。"""

    async def _fake(_msg: str) -> str:
        if isinstance(word, Exception):
            raise word
        return word

    monkeypatch.setattr(tc._ac, "classify_topic", _fake)


class TestClassifyVerdict:
    """三态判定矩阵 + 大小写/空白容忍。"""

    @pytest.mark.parametrize(
        "raw, verdict",
        [
            ("yes", "yes"),
            ("YES", "yes"),
            ("  Yes\n", "yes"),
            ("yes.", "yes"),  # 模型偶尔加标点
            ("yes please", "yes"),  # startswith yes
            ("no", "no"),
            ("NO", "no"),
            ("no, off-topic", "no"),
            ("uncertain", "uncertain"),
            ("UNCERTAIN", "uncertain"),
            ("garbage-output", "uncertain"),
            ("maybe", "uncertain"),  # 既非 yes 也非 no
            ("", "uncertain"),
        ],
    )
    async def test_verdict_parsing(self, monkeypatch, raw: str, verdict: str) -> None:
        _patch_classify(monkeypatch, raw)
        assert await tc.classify("hi") == verdict

    async def test_llm_failure_fail_open_uncertain(self, monkeypatch, caplog) -> None:
        _patch_classify(monkeypatch, RuntimeError("upstream down"))
        import logging

        with caplog.at_level(logging.WARNING, logger=tc.logger.name):
            v = await tc.classify("hi")
        assert v == "uncertain"
        assert any("classify failed" in rec.getMessage() for rec in caplog.records)

    async def test_llm_timeout_failure_fail_open(self, monkeypatch) -> None:
        _patch_classify(monkeypatch, TimeoutError("slow"))
        assert await tc.classify("hi") == "uncertain"

    async def test_unicode_message_passes_through(self, monkeypatch) -> None:
        """非 ASCII 消息也能被分类（仅检查我们没在 strip/lower 上炸）。"""
        _patch_classify(monkeypatch, "yes")
        assert await tc.classify("我想查询账户余额") == "yes"

    async def test_whitespace_only_output_uncertain(self, monkeypatch) -> None:
        _patch_classify(monkeypatch, "   \n\t")
        assert await tc.classify("hi") == "uncertain"


class TestRefusalText:
    """拒答文案改 i18n 后：C/B 端共享 refusal.c key，按 ui_locale 选语言。
    B 端默认 en，C 端跟随 APP；user_type 不再决定语种，只看 ui_locale。"""

    def test_c_user_chinese_when_zh_locale(self) -> None:
        msg = tc.refusal_text("c", "zh-Hant")
        assert "Tevau" in msg
        assert "账户" in msg or "卡片" in msg

    def test_b_user_english_default(self) -> None:
        # B 端不传 ui_locale → 默认 en
        msg = tc.refusal_text("b")
        assert msg.startswith("I'm Tevau's support assistant")
        assert "Open API" in msg

    @pytest.mark.parametrize("ut", ["g", "unknown", "", "ADMIN"])
    def test_unknown_user_type_still_resolves(self, ut: str) -> None:
        # user_type 不再决定文案，refusal_text 必须返回非空字符串
        msg = tc.refusal_text(ut)
        assert msg and "Tevau" in msg

    def test_ja_locale_returns_japanese(self) -> None:
        msg = tc.refusal_text("c", "ja")
        assert "Tevau" in msg
        assert "アシスタント" in msg or "ご質問" in msg


class TestUncertainHintConstant:
    """UNCERTAIN_HINT 文本契约（runtime 注入到 system block，不能为空）。"""

    def test_hint_not_empty(self) -> None:
        assert tc.UNCERTAIN_HINT
        assert isinstance(tc.UNCERTAIN_HINT, str)
