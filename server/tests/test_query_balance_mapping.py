import pytest


class FakeDB:
    def __init__(self, rows):
        self._rows = rows

    async def fetch_all(self, sql, params=(), limit=100):
        return list(self._rows)


@pytest.mark.asyncio
async def test_eur_and_status_and_plat(monkeypatch):
    import ai_engine.agent.tools.query_balance as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([
        dict(currency=6, money_type=1, total_count=5, status=1, account_no="A", plat_source=2)]))
    out = await m.run(user_id="1")
    b = out["balances"][0]
    assert b["currency"] == "EUR" and b["status"] == "冻结" and b["plat_source"] == "unlimitpay"


@pytest.mark.asyncio
async def test_unmapped_currency_marked(monkeypatch):
    # 真实库存在 currency=11（CurrencyEnum 未定义），必须显式标注而非吐裸数字
    import ai_engine.agent.tools.query_balance as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([
        dict(currency=11, money_type=1, total_count=691, status=0, account_no="A", plat_source=1)]))
    out = await m.run(user_id="1")
    assert out["balances"][0]["currency"] == "未知(11)"
