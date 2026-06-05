"""Tool: query_bu_order

被测对象：tools.query_bu_order.run
- 命中：order 列表 + 翻译 order_type / status。
- status=4(失败) → 触发卡级异常二级查询。
- third_card_id 为空/'-' → 不去查异常。
- 异常表无对应行 → failure_reason=None。
- 多笔失败订单 → 一次 IN 批查（消除 N+1）。
"""

import pytest

from ai_engine.agent.tools import query_bu_order as qbo
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    def __init__(self, orders=None, exceptions=None) -> None:
        self.orders = orders or []
        self.exceptions = exceptions or []
        self.exc_calls = 0

    async def fetch_one(self, *_a, **_k):  # noqa: ANN002,ANN003
        return None

    async def fetch_all(self, sql, _params, limit=100):  # noqa: ARG002
        if "trans_exception" in sql:
            self.exc_calls += 1
            return self.exceptions
        return self.orders


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(bdb, "get_db", lambda n: fake)
    monkeypatch.setattr(qbo, "get_db", lambda n: fake, raising=False)
    return fake


class TestQueryBuOrder:
    async def test_empty(self, fake_db) -> None:
        out = await qbo.run(tenant_id="1011010000068")
        assert out == {"orders": [], "count": 0}

    async def test_success_order_no_exception_lookup(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O1", "trade_order_sn": "T1", "order_type": 2,
            "status": 1, "trade_amount": "10", "fee": "0.1",
            "channel_amount": "10", "channel_fee": "0.1", "currency": "USD",
            "create_time": "2026-01-01", "end_time": None, "remark": None,
            "third_card_id": "CIDV-ABC",
        }]
        out = await qbo.run(tenant_id="1011010000068")
        o = out["orders"][0]
        assert o["order_type"] == "卡充值订单"
        assert o["status"] == "已完成"
        # 不触发异常查询
        assert fake_db.exc_calls == 0
        assert "failure_reason" not in o

    async def test_failed_order_triggers_exception_lookup(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O2", "trade_order_sn": "T2", "order_type": 1,
            "status": 4, "trade_amount": "20", "fee": None,
            "channel_amount": None, "channel_fee": None, "currency": "USD",
            "create_time": "2026-01-01", "end_time": None, "remark": "x",
            "third_card_id": "CIDV-XYZ",
        }]
        fake_db.exceptions = [{
            "card_id": "CIDV-XYZ",
            "reason": "卡组织拒绝",
            "error_trans_code": "DECL01",
            "trans_type": 4,
            "exception_type": 1,
            "create_time": "2026-01-01",
        }]
        out = await qbo.run(tenant_id="1011010000068")
        o = out["orders"][0]
        assert o["status"] == "失败"
        assert fake_db.exc_calls == 1
        assert o["failure_reason"]["reason"] == "卡组织拒绝"
        assert o["failure_reason"]["error_trans_code"] == "DECL01"
        assert o["failure_reason"]["exception_count"] == 1

    async def test_failed_order_no_third_card_id_skips_exception(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O3", "trade_order_sn": None, "order_type": 1,
            "status": 4, "trade_amount": None, "fee": None,
            "channel_amount": None, "channel_fee": None, "currency": None,
            "create_time": None, "end_time": None, "remark": None,
            "third_card_id": "",  # 空串
        }]
        out = await qbo.run(tenant_id="1011010000068")
        assert fake_db.exc_calls == 0
        assert out["orders"][0]["failure_reason"] is None

    async def test_failed_order_dash_third_card_id_skips_exception(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O4", "trade_order_sn": None, "order_type": 1,
            "status": 4, "trade_amount": None, "fee": None,
            "channel_amount": None, "channel_fee": None, "currency": None,
            "create_time": None, "end_time": None, "remark": None,
            "third_card_id": "-",
        }]
        out = await qbo.run(tenant_id="1011010000068")
        assert fake_db.exc_calls == 0
        assert out["orders"][0]["failure_reason"] is None

    async def test_failed_order_no_exception_row(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O5", "trade_order_sn": None, "order_type": 1,
            "status": 4, "trade_amount": None, "fee": None,
            "channel_amount": None, "channel_fee": None, "currency": None,
            "create_time": None, "end_time": None, "remark": None,
            "third_card_id": "CIDV-ZZZ",
        }]
        fake_db.exceptions = []
        out = await qbo.run(tenant_id="1011010000068")
        assert fake_db.exc_calls == 1
        assert out["orders"][0]["failure_reason"] is None

    async def test_unknown_order_type(self, fake_db) -> None:
        fake_db.orders = [{
            "order_sn": "O6", "trade_order_sn": None, "order_type": 99,
            "status": 6, "trade_amount": None, "fee": None,
            "channel_amount": None, "channel_fee": None, "currency": None,
            "create_time": None, "end_time": None, "remark": None,
            "third_card_id": None,
        }]
        out = await qbo.run(tenant_id="1011010000068")
        assert out["orders"][0]["order_type"] == "未知(99)"
        assert out["orders"][0]["status"] == "审核中"


class TestBatchExceptionQuery:
    """多笔失败订单共用一次 EXC_SQL 批查（消除 N+1）。"""

    async def test_three_failed_orders_one_exc_query(self, fake_db) -> None:
        fake_db.orders = [
            {"order_sn": "o1", "trade_order_sn": "to1", "order_type": 18, "status": 4,
             "trade_amount": "100", "fee": "1", "channel_amount": "100", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-01", "end_time": None,
             "remark": None, "third_card_id": "card-A"},
            {"order_sn": "o2", "trade_order_sn": "to2", "order_type": 18, "status": 4,
             "trade_amount": "200", "fee": "1", "channel_amount": "200", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-02", "end_time": None,
             "remark": None, "third_card_id": "card-B"},
            {"order_sn": "o3", "trade_order_sn": "to3", "order_type": 18, "status": 1,
             "trade_amount": "300", "fee": "1", "channel_amount": "300", "channel_fee": "0",
             "currency": "USD", "create_time": "2026-01-03", "end_time": None,
             "remark": None, "third_card_id": "card-C"},  # status=1 已完成，不查异常
        ]
        fake_db.exceptions = [
            {"card_id": "card-A", "reason": "insufficient funds",
             "error_trans_code": "E01", "trans_type": "PAY", "exception_type": 1,
             "create_time": "2026-01-01"},
            {"card_id": "card-B", "reason": "card frozen",
             "error_trans_code": "E02", "trans_type": "PAY", "exception_type": 1,
             "create_time": "2026-01-02"},
        ]
        out = await qbo.run(tenant_id="T1")
        assert fake_db.exc_calls == 1, (
            f"exception table queried {fake_db.exc_calls} times; expected 1 (batched)"
        )
        m = {o["order_sn"]: o for o in out["orders"]}
        assert m["o1"]["failure_reason"]["reason"] == "insufficient funds"
        assert m["o2"]["failure_reason"]["reason"] == "card frozen"
        assert "failure_reason" not in m["o3"]  # 非失败订单不查异常
