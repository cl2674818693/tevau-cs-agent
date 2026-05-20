from ai_engine.integrations.redact import (
    mask_card_no,
    mask_email,
    mask_id_card,
    mask_phone,
    scan_and_redact_text,
    scrub_dict,
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
    out = scrub_dict(
        raw,
        rules={
            "phone": mask_phone,
            "email": mask_email,
            "card_no": mask_card_no,
            "lock_reason": lambda s: "风控规则命中" if s else s,
        },
    )
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
