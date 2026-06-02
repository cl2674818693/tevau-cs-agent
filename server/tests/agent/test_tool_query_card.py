"""Tool: query_card

被测对象：tools.query_card.run + _card_view
- 多张卡 + status 翻译。
- 冻结/锁定态卡（status ∈ _FROZEN_STATUSES = {2,7,9}）触发 FREEZE_SQL 二级查询。
- 非冻结态卡不查冻结历史。
- unmask=False → 卡号脱敏；unmask=True → 卡号原值。
- 空查询：cards=[], count=0。
"""

import pytest

from ai_engine.agent.tools import query_card as qc
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    """支持两类调用：fetch_all(SQL, params) 按 sql 关键字分发。"""

    def __init__(self, cards: list[dict] | None = None, freezes: list[dict] | None = None) -> None:
        self.cards = cards or []
        self.freezes = freezes or []
        self.freeze_calls = 0

    async def fetch_one(self, *_a, **_k):  # noqa: ANN002,ANN003
        return None

    async def fetch_all(self, sql, _params, limit=100):  # noqa: ARG002
        if "freeze_history" in sql:
            self.freeze_calls += 1
            return self.freezes
        return self.cards


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(bdb, "get_db", lambda n: fake)
    monkeypatch.setattr(qc, "get_db", lambda n: fake, raising=False)
    return fake


class TestQueryCard:
    async def test_empty(self, fake_db) -> None:
        out = await qc.run(user_id="1")
        assert out == {"cards": [], "count": 0, "unmasked": False}

    async def test_card_active_no_freeze_lookup(self, fake_db) -> None:
        fake_db.cards = [{
            "id": 100, "card_number": "4938750672464590",
            "card_status": 0, "card_status_description": "ok",
            "card_balance": "10.00", "card_currency": 2,
            "card_type": 2, "expiry_date": "2030-01-01",
            "reject_reason": None, "cancel_card_reason": None,
            "card_alias_name": "alias", "active_time": None, "create_time": None,
        }]
        out = await qc.run(user_id="1")
        assert out["count"] == 1
        c = out["cards"][0]
        assert c["status"] == "开卡成功"
        assert c["currency"] == "USD"
        # 默认脱敏
        assert "4938" in c["card_no"]
        assert "4590" in c["card_no"]
        assert "****" in c["card_no"]
        # 未触发 freeze 查询
        assert fake_db.freeze_calls == 0

    async def test_frozen_card_triggers_freeze_lookup(self, fake_db) -> None:
        fake_db.cards = [{
            "id": 200, "card_number": "1111222233334444",
            "card_status": 9, "card_status_description": None,
            "card_balance": "0", "card_currency": 2,
            "card_type": 1, "expiry_date": None,
            "reject_reason": None, "cancel_card_reason": None,
            "card_alias_name": None, "active_time": None, "create_time": None,
        }]
        fake_db.freezes = [{
            "freeze_reason": 4,  # 人工冻结卡
            "reason_desc": "客户疑似盗刷",
            "create_time": "2026-01-01 00:00:00",
            "auto_unfreeze_time": None,
        }]
        out = await qc.run(user_id="1")
        c = out["cards"][0]
        assert c["status"] == "卡片冻结"
        assert c["freeze_reason"] == "人工冻结卡"
        assert c["freeze_reason_desc"] == "客户疑似盗刷"
        assert fake_db.freeze_calls == 1

    async def test_locked_status_also_triggers_freeze_query(self, fake_db) -> None:
        fake_db.cards = [{
            "id": 1, "card_number": "4938750672464590",
            "card_status": 2,  # 已锁定
            "card_status_description": None, "card_balance": None, "card_currency": 2,
            "card_type": 2, "expiry_date": None, "reject_reason": None,
            "cancel_card_reason": None, "card_alias_name": None,
            "active_time": None, "create_time": None,
        }]
        fake_db.freezes = []  # 无冻结历史，主表照常返回但不带 freeze 字段
        out = await qc.run(user_id="1")
        assert fake_db.freeze_calls == 1
        assert "freeze_reason" not in out["cards"][0]  # 无 freeze 行就不写

    async def test_unmask_returns_card_no(self, fake_db) -> None:
        fake_db.cards = [{
            "id": 1, "card_number": "4938750672464590",
            "card_status": 0, "card_status_description": None,
            "card_balance": None, "card_currency": 2,
            "card_type": 2, "expiry_date": None, "reject_reason": None,
            "cancel_card_reason": None, "card_alias_name": None,
            "active_time": None, "create_time": None,
        }]
        out = await qc.run(user_id="1", unmask=True)
        assert out["cards"][0]["card_no"] == "4938750672464590"
        assert out["unmasked"] is True

    async def test_unknown_card_status_labeled(self, fake_db) -> None:
        fake_db.cards = [{
            "id": 1, "card_number": "4938750672464590",
            "card_status": 999, "card_status_description": None,
            "card_balance": None, "card_currency": 0,
            "card_type": None, "expiry_date": None, "reject_reason": None,
            "cancel_card_reason": None, "card_alias_name": None,
            "active_time": None, "create_time": None,
        }]
        out = await qc.run(user_id="1")
        assert out["cards"][0]["status"] == "未知(999)"
        assert out["cards"][0]["currency"] == "UNKNOWN"  # 0 in dict
