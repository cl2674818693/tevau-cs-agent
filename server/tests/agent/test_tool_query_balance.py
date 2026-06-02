"""Tool: query_balance

被测对象：tools.query_balance.run
- 多币种行 → 数组；count 正确。
- 枚举：money_type / currency / status / plat_source 翻译。
- 未知 currency → 标 未知(原值)。
- unmask=False → account_no=None；unmask=True → 返回真实账号。
- 空查询：rows=[] → balances=[], count=0。
"""

import pytest

from ai_engine.agent.tools import query_balance as qb
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []

    async def fetch_one(self, *_a, **_k):  # noqa: ANN002,ANN003
        return None

    async def fetch_all(self, _sql, _params, limit=100):  # noqa: ARG002
        return self.rows


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(bdb, "get_db", lambda n: fake)
    monkeypatch.setattr(qb, "get_db", lambda n: fake, raising=False)
    return fake


class TestQueryBalance:
    async def test_empty(self, fake_db) -> None:
        out = await qb.run(user_id="1")
        assert out == {"balances": [], "count": 0, "unmasked": False}

    async def test_multi_currency_translate(self, fake_db) -> None:
        fake_db.rows = [
            {"money_type": 1, "currency": 2, "total_count": "100.50",
             "status": 0, "account_no": "acc-1", "plat_source": 1},
            {"money_type": 2, "currency": 1, "total_count": "0.0",
             "status": 1, "account_no": "acc-2", "plat_source": 3},
        ]
        out = await qb.run(user_id="1")
        assert out["count"] == 2
        b = out["balances"]
        assert b[0]["currency"] == "USD"
        assert b[0]["money_type"] == "现金"
        assert b[0]["status"] == "正常"
        assert b[0]["plat_source"] == "tevau"
        assert b[1]["currency"] == "USDT"
        assert b[1]["money_type"] == "在途"
        assert b[1]["plat_source"] == "skydaopay"

    async def test_unknown_currency_labeled(self, fake_db) -> None:
        fake_db.rows = [{"money_type": 1, "currency": 11, "total_count": "1",
                         "status": 0, "account_no": None, "plat_source": 1}]
        out = await qb.run(user_id="1")
        # 库里 currency=11 未在 enum；应被标 未知(11)
        assert out["balances"][0]["currency"] == "未知(11)"

    async def test_account_no_masked_by_default(self, fake_db) -> None:
        fake_db.rows = [{"money_type": 1, "currency": 2, "total_count": "1",
                         "status": 0, "account_no": "ACC-SECRET", "plat_source": 1}]
        out = await qb.run(user_id="1")
        assert out["balances"][0]["account_no"] is None
        assert out["unmasked"] is False

    async def test_account_no_visible_when_unmask(self, fake_db) -> None:
        fake_db.rows = [{"money_type": 1, "currency": 2, "total_count": "1",
                         "status": 0, "account_no": "ACC-SECRET", "plat_source": 1}]
        out = await qb.run(user_id="1", unmask=True)
        assert out["balances"][0]["account_no"] == "ACC-SECRET"
        assert out["unmasked"] is True

    async def test_null_total_count_returns_none_amount(self, fake_db) -> None:
        fake_db.rows = [{"money_type": 1, "currency": 2, "total_count": None,
                         "status": 0, "account_no": None, "plat_source": 1}]
        out = await qb.run(user_id="1")
        assert out["balances"][0]["amount"] is None

    async def test_db_error_propagates(self, monkeypatch) -> None:
        class _Boom(_FakeDB):
            async def fetch_all(self, *_a, **_k):  # noqa: ANN002,ANN003
                raise RuntimeError("db dead")

        fake = _Boom()
        monkeypatch.setattr(qb, "get_db", lambda n: fake, raising=False)
        with pytest.raises(RuntimeError, match="db dead"):
            await qb.run(user_id="1")
