"""Tool: query_transaction

被测对象：tools.query_transaction.run
- 卡交易 + 钱包流水两段查询；count 分开统计。
- 枚举翻译：type / status / flow / currency / pay_type / wallet_*。
- 空查询：均 0；返回 note 提示两者都空才说明该用户无交易。
"""

import pytest

from ai_engine.agent.tools import query_transaction as qt
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    """按 sql 分发：含 wallet_records 返回 wallet rows；否则 card rows。"""

    def __init__(self, card_rows=None, wallet_rows=None) -> None:
        self.card_rows = card_rows or []
        self.wallet_rows = wallet_rows or []

    async def fetch_one(self, *_a, **_k):  # noqa: ANN002,ANN003
        return None

    async def fetch_all(self, sql, _params, limit=100):  # noqa: ARG002
        if "wallet_records" in sql:
            return self.wallet_rows
        return self.card_rows


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(bdb, "get_db", lambda n: fake)
    monkeypatch.setattr(qt, "get_db", lambda n: fake, raising=False)
    return fake


class TestQueryTransaction:
    async def test_empty(self, fake_db) -> None:
        out = await qt.run(user_id="1")
        assert out["card_count"] == 0
        assert out["wallet_count"] == 0
        assert "都为空" in out["note"]

    async def test_card_tx_translated(self, fake_db) -> None:
        fake_db.card_rows = [{
            "type": 4, "digest": 2, "status": 3, "currency": 2,
            "trade_amount": "10.50", "income_amount": None, "out_amount": "10.50",
            "fee": "0.10", "merchant_name": "Amazon",
            "remark": "purchase", "order_id": "ord-1", "pay_type": 3,
            "tx_time": "2026-01-01 00:00:00", "card_number": "4938****4590",
        }]
        out = await qt.run(user_id="1")
        c = out["card_transactions"][0]
        assert c["type"] == "卡消费"
        assert c["flow"] == "出账"
        assert c["status"] == "成功"
        assert c["currency"] == "USD"
        assert c["channel"] == "reap"
        assert c["merchant"] == "Amazon"

    async def test_wallet_tx_translated(self, fake_db) -> None:
        fake_db.wallet_rows = [{
            "type": 1, "transaction_status": 3, "fund_flow": 1,
            "trade_amount": "100", "fee": "0", "currency": 2,
            "create_time": "2026-02-02 00:00:00",
        }]
        out = await qt.run(user_id="1")
        w = out["wallet_flows"][0]
        assert w["type"] == "充币"
        assert w["status"] == "成功"
        assert w["flow"] == "入账"
        assert w["currency"] == "USD"

    async def test_both_arrays_independent(self, fake_db) -> None:
        fake_db.card_rows = [{
            "type": 4, "digest": 2, "status": 3, "currency": 2,
            "trade_amount": "1", "income_amount": None, "out_amount": "1",
            "fee": None, "merchant_name": None, "remark": None,
            "order_id": None, "pay_type": None,
            "tx_time": None, "card_number": None,
        }]
        fake_db.wallet_rows = [
            {"type": 1, "transaction_status": 3, "fund_flow": 1,
             "trade_amount": "10", "fee": "0", "currency": 2, "create_time": None},
            {"type": 2, "transaction_status": 4, "fund_flow": 2,
             "trade_amount": "5", "fee": "0", "currency": 2, "create_time": None},
        ]
        out = await qt.run(user_id="1")
        assert out["card_count"] == 1
        assert out["wallet_count"] == 2

    async def test_unknown_type_labeled(self, fake_db) -> None:
        fake_db.card_rows = [{
            "type": 999, "digest": 1, "status": -1, "currency": 99,
            "trade_amount": "1", "income_amount": None, "out_amount": None,
            "fee": None, "merchant_name": None, "remark": None,
            "order_id": None, "pay_type": 99,
            "tx_time": None, "card_number": None,
        }]
        out = await qt.run(user_id="1")
        c = out["card_transactions"][0]
        assert c["type"] == "未知(999)"
        assert c["status"] == "未知"  # -1 → "未知"
        assert c["currency"] == "未知(99)"
        assert c["channel"] == "未知(99)"

    async def test_db_failure_propagates(self, monkeypatch) -> None:
        class _Boom(_FakeDB):
            async def fetch_all(self, *_a, **_k):  # noqa: ANN002,ANN003
                raise RuntimeError("db dead")

        fake = _Boom()
        monkeypatch.setattr(qt, "get_db", lambda n: fake, raising=False)
        with pytest.raises(RuntimeError, match="db dead"):
            await qt.run(user_id="1")
