import pytest


class FakeDB:
    def __init__(self, row): self._row = row
    async def fetch_one(self, sql, params=()): return self._row


@pytest.mark.asyncio
async def test_kyc_status_correct(monkeypatch):
    import ai_engine.agent.tools.query_user as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        dict(id=1, user_code="C1", email_address=None, mobile_phone=None, nick_name="n",
             user_status=0, kyc_status=0, open_card_status=0,
             registration_time=None, last_login_time=None)))
    out = await m.run(user_id="1")
    assert out["user"]["kyc_status"] == "未认证"


@pytest.mark.asyncio
async def test_kyc_status_3_is_reviewing(monkeypatch):
    import ai_engine.agent.tools.query_user as m
    monkeypatch.setattr(m, "get_db", lambda name: FakeDB(
        dict(id=1, user_code="C1", email_address=None, mobile_phone=None, nick_name="n",
             user_status=0, kyc_status=3, open_card_status=0,
             registration_time=None, last_login_time=None)))
    out = await m.run(user_id="1")
    assert out["user"]["kyc_status"] == "审核中"
