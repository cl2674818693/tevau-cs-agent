import pytest


class FakeOne:
    def __init__(self, row):
        self._row = row

    async def fetch_one(self, sql, params=()):
        return self._row


@pytest.mark.asyncio
async def test_audit_status_5_uncertified(monkeypatch):
    import ai_engine.agent.tools.query_kyc as m

    monkeypatch.setattr(
        m,
        "get_db",
        lambda name: FakeOne(
            dict(
                audit_status=5,
                identity_failer_reason=None,
                certification_status=0,
                country_area="SG",
                live_country="SG",
                identity_card_type=2,
                first_name="A",
                last_name="B",
                identity_card="X",
                birthday=None,
                phone_code="65",
                phone_number="123",
                address=None,
                city=None,
                post_code=None,
                request_time=None,
                audit_pass_time=None,
                user_kyc_status=0,
            )
        ),
    )
    out = await m.run(user_id="1")
    assert out["kyc"]["audit_status"] == "未认证"


@pytest.mark.asyncio
async def test_audit_status_3_not_submitted(monkeypatch):
    import ai_engine.agent.tools.query_kyc as m

    monkeypatch.setattr(
        m,
        "get_db",
        lambda name: FakeOne(
            dict(
                audit_status=3,
                identity_failer_reason=None,
                certification_status=0,
                country_area=None,
                live_country=None,
                identity_card_type=2,
                first_name="A",
                last_name="B",
                identity_card="X",
                birthday=None,
                phone_code=None,
                phone_number=None,
                address=None,
                city=None,
                post_code=None,
                request_time=None,
                audit_pass_time=None,
                user_kyc_status=0,
            )
        ),
    )
    out = await m.run(user_id="1")
    assert out["kyc"]["audit_status"] == "未提审"


@pytest.mark.asyncio
async def test_user_kyc_status_surfaced(monkeypatch):
    import ai_engine.agent.tools.query_kyc as m

    monkeypatch.setattr(
        m,
        "get_db",
        lambda name: FakeOne(
            dict(
                audit_status=1,
                identity_failer_reason=None,
                certification_status=1,
                country_area="SG",
                live_country="SG",
                identity_card_type=2,
                first_name="A",
                last_name="B",
                identity_card="X",
                birthday=None,
                phone_code="65",
                phone_number="123",
                address=None,
                city=None,
                post_code=None,
                request_time=None,
                audit_pass_time=None,
                user_kyc_status=1,
            )
        ),
    )
    out = await m.run(user_id="1")
    assert out["kyc"]["user_kyc_status"] == "已认证"
