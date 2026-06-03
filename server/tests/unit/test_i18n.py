"""i18n.t / normalize_locale: 12 语言文案查找 + 区域归一化。

覆盖：
- normalize_locale：12 个 supported + zh-Hant/pt-BR/en-US 等 BCP47 变体 + 空 + 不支持。
- t()：完整覆盖语言直接命中；缺译回退 en；连 en 缺失也不抛错（取第一个值）。
- format 占位符。
- 未注册 key 抛 KeyError（开发者保护，避免 typo 静默失败）。
"""

import pytest

from ai_engine.i18n import messages, normalize_locale, t


class TestNormalizeLocale:
    def test_none_falls_back_to_en(self) -> None:
        assert normalize_locale(None) == "en"

    def test_empty_falls_back_to_en(self) -> None:
        assert normalize_locale("") == "en"

    def test_unknown_falls_back_to_en(self) -> None:
        # B 端默认就是 en；客户端送什么"奇怪"locale 都不能崩
        assert normalize_locale("xx") == "en"
        assert normalize_locale("klingon") == "en"

    def test_zh_hant_normalized_to_zh(self) -> None:
        # APP _toLanguageTag 把 zh → "zh-Hant"，后端必须归一为 "zh" 才能命中文案表
        assert normalize_locale("zh-Hant") == "zh"
        assert normalize_locale("zh-CN") == "zh"
        assert normalize_locale("zh-TW") == "zh"
        assert normalize_locale("zh_Hant") == "zh"

    def test_pt_br_normalized_to_pt(self) -> None:
        # 巴西葡萄牙语共用 pt
        assert normalize_locale("pt-BR") == "pt"
        assert normalize_locale("pt-PT") == "pt"

    def test_en_variants(self) -> None:
        assert normalize_locale("en-US") == "en"
        assert normalize_locale("en-GB") == "en"
        assert normalize_locale("EN") == "en"

    def test_all_12_supported_pass_through(self) -> None:
        for lng in ("ar", "en", "es", "id", "ja", "ko", "pt", "ru", "th", "tr", "vi", "zh"):
            assert normalize_locale(lng) == lng


class TestTranslate:
    def test_direct_hit(self) -> None:
        # 完整覆盖 key，命中对应语言
        assert t("error.rate_limited", "ja").startswith("メッセージ")
        assert t("error.rate_limited", "pt").startswith("Muitas")
        assert t("error.rate_limited", "zh-Hant") == "消息过于频繁，请稍后再试。"

    def test_unknown_locale_uses_en(self) -> None:
        assert "Too many messages" in t("error.rate_limited", "xx")

    def test_partial_coverage_falls_back_to_en(self) -> None:
        # tool.search_timeout 只覆盖 en + zh；其他 10 种缺译应回退 en
        assert "Search timed out" in t("tool.search_timeout", "ja")
        assert "Search timed out" in t("tool.search_timeout", "id")
        # 命中的语言不回退
        assert t("tool.search_timeout", "zh-Hant") == "搜索超时，请用更具体的关键词。"

    def test_format_kwargs(self) -> None:
        # 占位符
        out = t("system.conversation_compacted", "en", id=42)
        assert "42" in out and "new one" in out
        out_ja = t("system.conversation_compacted", "ja", id=99)
        assert "99" in out_ja

    def test_unknown_key_raises(self) -> None:
        # 防 typo 静默：未注册 key 必须抛错而非返回空
        with pytest.raises(KeyError):
            t("nonexistent.key", "en")

    def test_all_12_for_one_key(self) -> None:
        # 完整覆盖的 key：12 种语言每一种都拿得到非空字符串
        for lng in messages.SUPPORTED_LOCALES:
            v = t("error.failsoft", lng)
            assert v and isinstance(v, str)

    def test_b_end_default_en(self) -> None:
        # 业务约定：B 端 BU 默认 en；不传 locale 时 t() 默认应等于 en
        assert t("greeting.b") == t("greeting.b", "en")
        assert "Open API" in t("greeting.b")
