import pytest


class FakeDB:
    def __init__(self, rows):
        self._rows = rows

    async def fetch_all(self, sql, params=(), limit=100):
        return list(self._rows)

    async def fetch_one(self, sql, params=()):
        return self._rows[0] if self._rows else None


@pytest.mark.asyncio
async def test_card_reward_mapped(monkeypatch):
    import ai_engine.agent.tools.query_transaction as m

    card_rows = [dict(type=29, digest=2, status=3, currency=2, trade_amount=10,
                      income_amount=None, out_amount=10, fee=0, merchant_name=None,
                      remark="Bonus expired", order_id="RE1", card_number="****0823",
                      tx_time="2026-04-25 10:40:37", pay_type=3)]
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(card_rows))
    out = await m.run(user_id="1")
    t = out["card_transactions"][0]
    assert t["type"] == "奖励" and t["flow"] == "出账"
    assert t["status"] == "成功" and t["currency"] == "USD"
    assert t["channel"] == "reap"


@pytest.mark.asyncio
async def test_unknown_type_marked(monkeypatch):
    import ai_engine.agent.tools.query_transaction as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([dict(type=999, digest=1,
        status=3, currency=2, trade_amount=1, income_amount=1, out_amount=None, fee=0,
        merchant_name=None, remark=None, order_id="x", card_number=None,
        tx_time=None, pay_type=3)]))
    out = await m.run(user_id="1")
    assert out["card_transactions"][0]["type"] == "未知(999)"
