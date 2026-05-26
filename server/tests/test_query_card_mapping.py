import pytest


class FakeDB:
    def __init__(self, cards, freezes):
        self.cards = cards
        self.freezes = freezes
        self.calls = []

    async def fetch_all(self, sql, params=(), limit=100):
        self.calls.append((sql, params))
        if "t_tevaupay_bank_card_freeze_history" in sql:
            return list(self.freezes)
        return list(self.cards)


def _card(**over):
    base = dict(
        id=1,
        card_number="****0823",
        card_status=0,
        card_status_description=None,
        card_balance=0,
        card_currency=2,
        card_type=1,
        expiry_date=None,
        reject_reason=None,
        cancel_card_reason=None,
        card_alias_name=None,
        active_time=None,
        create_time=None,
        three_card_id="T1",
    )
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_card_status_14_pending_activate(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_card(card_status=14)], []))
    out = await m.run(user_id="1")
    assert out["cards"][0]["status"] == "待激活"


@pytest.mark.asyncio
async def test_card_status_13_adding(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_card(card_status=13)], []))
    out = await m.run(user_id="1")
    assert out["cards"][0]["status"] == "添加中"


@pytest.mark.asyncio
async def test_currency_3_is_arb_eth(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_card(card_currency=3)], []))
    out = await m.run(user_id="1")
    assert out["cards"][0]["currency"] == "ARB_ETH"


@pytest.mark.asyncio
async def test_currency_6_eur(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    monkeypatch.setattr(m, "get_db", lambda name: FakeDB([_card(card_currency=6)], []))
    out = await m.run(user_id="1")
    assert out["cards"][0]["currency"] == "EUR"


@pytest.mark.asyncio
async def test_frozen_card_attaches_reason(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    monkeypatch.setattr(
        m,
        "get_db",
        lambda name: FakeDB(
            [_card(card_status=9, card_status_description="x")],
            [
                dict(
                    freeze_reason=1,
                    reason_desc="黑名单商户交易",
                    create_time="2026-05-01 00:00:00",
                    auto_unfreeze_time="2026-05-02 00:00:00",
                )
            ],
        ),
    )
    out = await m.run(user_id="1")
    card = out["cards"][0]
    assert card["freeze_reason"] is not None
    assert card["freeze_reason"] == "黑名单商户交易"
    assert card["freeze_reason_desc"] == "黑名单商户交易"


@pytest.mark.asyncio
async def test_non_frozen_card_no_freeze_query(monkeypatch):
    import ai_engine.agent.tools.query_card as m

    db = FakeDB([_card(card_status=0)], [])
    monkeypatch.setattr(m, "get_db", lambda name: db)
    out = await m.run(user_id="1")
    # 非冻结卡不应触发冻结表查询
    assert not any("t_tevaupay_bank_card_freeze_history" in c[0] for c in db.calls)
    assert out["cards"][0].get("freeze_reason") is None
