from ai_engine.agent.tools.base import label, scope_note

def test_label_maps_known():
    assert label({1: "USDT", 2: "USD"}, 2) == "USD"

def test_label_marks_unknown_value():
    assert label({1: "USDT"}, 7) == "未知(7)"

def test_label_none_stays_none():
    assert label({1: "USDT"}, None) is None

def test_scope_note_for_empty():
    note = scope_note("钱包流水", covered="钱包充值/提现/转账", not_covered="卡消费/奖励")
    assert "未覆盖" in note and "卡消费" in note
