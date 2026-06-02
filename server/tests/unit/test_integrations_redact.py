"""Unit tests: integrations.redact

被测对象：PII 脱敏工具（mask_phone/id_card/card_no/email）+ 结构递归（scrub_dict）+
LLM 输出兜底正则扫描（scan_and_redact_text，含风控规则 R-xxx）。
纯函数无外部依赖，直接断言输入输出。
"""

import pytest

from ai_engine.integrations import redact as r


class TestMaskPhone:
    """spec §5.4：保留前 3 + 后 2，中间 ****。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("13812345678", "138****78"),
            ("18900001111", "189****11"),
            ("12345678", "123****78"),  # 8 位（>=7）：仍按规则
            ("1234567", "123****67"),  # 7 位边界
        ],
    )
    def test_normal(self, raw: str, expected: str) -> None:
        assert r.mask_phone(raw) == expected

    @pytest.mark.parametrize("raw", ["", None])
    def test_empty_returns_empty_string(self, raw: str | None) -> None:
        assert r.mask_phone(raw) == ""

    @pytest.mark.parametrize("raw", ["1", "12", "123456"])
    def test_short_returns_all_star(self, raw: str) -> None:
        # < 7 全部打星
        assert r.mask_phone(raw) == "*" * len(raw)


class TestMaskIdCard:
    """spec §5.4：保留前 2 + 后 2，中间全 *。"""

    def test_18_digit(self) -> None:
        assert r.mask_id_card("110101199001011234") == "11" + "*" * 14 + "34"

    def test_18_with_x(self) -> None:
        assert r.mask_id_card("11010119900101123X") == "11" + "*" * 14 + "3X"

    def test_six_digits_boundary(self) -> None:
        assert r.mask_id_card("123456") == "12**56"

    @pytest.mark.parametrize("raw", ["", None])
    def test_empty(self, raw: str | None) -> None:
        assert r.mask_id_card(raw) == ""

    @pytest.mark.parametrize("raw", ["1", "12345"])
    def test_short_returns_all_star(self, raw: str) -> None:
        assert r.mask_id_card(raw) == "*" * len(raw)


class TestMaskCardNo:
    """卡号：保留前 4 + 后 4；先剥离非数字字符。"""

    def test_normal_16(self) -> None:
        assert r.mask_card_no("6225880123456789") == "6225 **** **** 6789"

    def test_with_spaces(self) -> None:
        assert r.mask_card_no("6225 8801 2345 6789") == "6225 **** **** 6789"

    def test_with_hyphens(self) -> None:
        assert r.mask_card_no("6225-8801-2345-6789") == "6225 **** **** 6789"

    def test_19_digit_amex_like(self) -> None:
        assert r.mask_card_no("1234567890123456789") == "1234 **** **** 6789"

    def test_short_returns_all_star_digits_only(self) -> None:
        # 全角空格不会被 \D 剥离？实测 \D 匹配的是 ASCII 非数字，全角也算
        assert r.mask_card_no("123-456") == "*" * 6  # 只剩 6 位 < 10

    @pytest.mark.parametrize("raw", ["", None])
    def test_empty(self, raw: str | None) -> None:
        assert r.mask_card_no(raw) == ""


class TestMaskEmail:
    """本地名保留 2 字符 + ***。"""

    def test_normal(self) -> None:
        assert r.mask_email("alice@example.com") == "al***@example.com"

    def test_short_local(self) -> None:
        assert r.mask_email("ab@x.com") == "ab***@x.com"

    def test_single_char_local(self) -> None:
        assert r.mask_email("a@x.com") == "*@x.com"

    @pytest.mark.parametrize("raw", ["", None])
    def test_empty(self, raw: str | None) -> None:
        assert r.mask_email(raw) == ""

    def test_no_at_sign_returns_all_star(self) -> None:
        assert r.mask_email("nothing-special") == "*" * len("nothing-special")


class TestScrubDict:
    """按字段名规则递归脱敏 dict / list 结构。"""

    def test_top_level_field_masked(self) -> None:
        rules = {"phone": r.mask_phone}
        out = r.scrub_dict({"phone": "13812345678", "name": "alice"}, rules)
        assert out == {"phone": "138****78", "name": "alice"}

    def test_nested_dict_recurses(self) -> None:
        rules = {"phone": r.mask_phone}
        out = r.scrub_dict({"user": {"phone": "13800001111"}}, rules)
        assert out["user"]["phone"] == "138****11"

    def test_list_of_dict_recurses(self) -> None:
        rules = {"email": r.mask_email}
        out = r.scrub_dict(
            {"contacts": [{"email": "a@x.com"}, {"email": "bob@x.com"}]},
            rules,
        )
        assert out["contacts"][0]["email"] == "*@x.com"
        assert out["contacts"][1]["email"] == "bo***@x.com"

    def test_non_string_value_for_matched_key_recurses(self) -> None:
        """如果 key 命中但 value 不是 str，应走递归路径（不会报错）。"""
        rules = {"phone": r.mask_phone}
        out = r.scrub_dict({"phone": {"nested": "13812345678"}}, rules)
        # 嵌套 dict 进一步递归；nested key 不在规则里，所以原样
        assert out == {"phone": {"nested": "13812345678"}}

    def test_non_dict_non_list_returned_as_is(self) -> None:
        assert r.scrub_dict("plain", {}) == "plain"
        assert r.scrub_dict(123, {}) == 123
        assert r.scrub_dict(None, {}) is None

    def test_empty_dict_and_list(self) -> None:
        assert r.scrub_dict({}, {"x": r.mask_phone}) == {}
        assert r.scrub_dict([], {"x": r.mask_phone}) == []


class TestScanAndRedactText:
    """LLM 输出兜底扫描：手机/身份证/卡号/邮箱/风控规则。"""

    def test_phone_in_sentence(self) -> None:
        out = r.scan_and_redact_text("我的电话是 13812345678，请回拨。")
        assert "138****78" in out
        assert "13812345678" not in out

    def test_id_card_with_x(self) -> None:
        out = r.scan_and_redact_text("身份证 11010119900101123X 用于实名。")
        # 18 位 → mask 后 "11" + 14*"*" + "3X"
        assert "11" + "*" * 14 + "3X" in out

    def test_card_no_with_spaces(self) -> None:
        out = r.scan_and_redact_text("卡号 6225 8801 2345 6789 已绑定。")
        assert "6225 **** **** 6789" in out
        assert "6225 8801 2345 6789" not in out

    def test_card_no_continuous(self) -> None:
        out = r.scan_and_redact_text("test 6225880123456789 ok")
        assert "6225 **** **** 6789" in out

    def test_email_in_text(self) -> None:
        out = r.scan_and_redact_text("contact alice@example.com for details")
        assert "al***@example.com" in out
        assert "alice@example.com" not in out

    def test_risk_rule_replaced(self) -> None:
        out = r.scan_and_redact_text("命中 R-001 与 R-1234，需复核。")
        assert "R-001" not in out
        assert "R-1234" not in out
        assert out.count("[风控规则]") == 2

    def test_mixed_pii_in_one_paragraph(self) -> None:
        text = (
            "用户 alice@x.com（手机 13900001111，身份证 110101199001011234，"
            "卡 6225-8801-2345-6789）命中 R-007。"
        )
        out = r.scan_and_redact_text(text)
        assert "alice@x.com" not in out
        assert "13900001111" not in out
        assert "110101199001011234" not in out
        assert "6225-8801-2345-6789" not in out
        assert "R-007" not in out
        assert "[风控规则]" in out

    def test_empty_text(self) -> None:
        assert r.scan_and_redact_text("") == ""

    def test_pure_chinese_no_change(self) -> None:
        assert r.scan_and_redact_text("你好世界") == "你好世界"

    def test_phone_not_match_starts_with_2(self) -> None:
        """规则：1[3-9]\\d{9}；以 2 开头的 11 位不算手机号，应保留。"""
        out = r.scan_and_redact_text("订单 28812345678 已生成")
        # 但 28812345678 是 11 位连续数字 → 可能被卡号规则 \d{13,19} 捕获？11 < 13，故不会。
        assert "28812345678" in out

    def test_id_card_before_card_priority(self) -> None:
        """注释说"先于卡号"以保 X 结尾正确归类：18 位含 X 应走身份证。"""
        out = r.scan_and_redact_text("证件 11010119900101123X 提交")
        # 不应该被卡号兜底（卡号规则 \d{13,19} 不含 X）
        assert "11" in out and "3X" in out
