"""Tool: query_kyc

被测对象：tools.query_kyc.run
- 命中：脱敏证件/手机 + 翻译 audit_status / user_kyc_status / id_type。
- 未命中：{kyc: None, note}。
- unmask=True：full_name/identity_card/birthday/phone/address 全字段。
- user_kyc_status 不一致 note 提示以 user_kyc_status 为准。
"""

import pytest

from ai_engine.agent.tools import query_kyc as qk
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    def __init__(self, row=None) -> None:
        self.row = row

    async def fetch_one(self, *_a, **_k):  # noqa: ANN002,ANN003
        return self.row

    async def fetch_all(self, *_a, **_k):  # noqa: ANN002,ANN003
        return []


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()
    monkeypatch.setattr(bdb, "get_db", lambda n: fake)
    monkeypatch.setattr(qk, "get_db", lambda n: fake, raising=False)
    return fake


class TestQueryKyc:
    async def test_no_record(self, fake_db) -> None:
        out = await qk.run(user_id="1")
        assert out["kyc"] is None
        assert "无 KYC 记录" in out["note"]

    async def test_masked_default(self, fake_db) -> None:
        fake_db.row = {
            "audit_status": 1, "identity_failer_reason": None,
            "certification_status": 1, "country_area": "CN",
            "live_country": "CN", "identity_card_type": 1,
            "first_name": "三", "last_name": "张",
            "identity_card": "11010119900307123X",
            "birthday": "1990-03-07",
            "phone_code": "86", "phone_number": "13812345678",
            "address": "北京海淀", "city": "北京", "post_code": "100000",
            "request_time": None, "audit_pass_time": None,
            "user_kyc_status": 1,
        }
        out = await qk.run(user_id="1", unmask=False)
        k = out["kyc"]
        assert k["user_kyc_status"] == "已认证"
        assert k["audit_status"] == "认证通过"
        assert k["id_type"] == "身份证"
        # 身份证脱敏：前 2 + 后 2
        assert k["identity_card"].startswith("11")
        assert k["identity_card"].endswith("3X")
        assert "*" in k["identity_card"]
        # 手机：前 3 + 后 2
        assert k["phone"].startswith("138")
        assert k["phone"].endswith("78")
        assert "full_name" not in k  # 高敏字段隐藏
        assert k["pii_note"]

    async def test_unmask_returns_full_pii(self, fake_db) -> None:
        fake_db.row = {
            "audit_status": 2, "identity_failer_reason": "活体失败",
            "certification_status": 0, "country_area": "CN",
            "live_country": "CN", "identity_card_type": 1,
            "first_name": "三", "last_name": "张",
            "identity_card": "11010119900307123X",
            "birthday": "1990-03-07",
            "phone_code": "86", "phone_number": "13812345678",
            "address": "北京海淀", "city": "北京", "post_code": "100000",
            "request_time": "2026-01-01 00:00:00", "audit_pass_time": None,
            "user_kyc_status": 0,
        }
        out = await qk.run(user_id="1", unmask=True)
        k = out["kyc"]
        assert k["full_name"] == "张三"
        assert k["identity_card"] == "11010119900307123X"
        assert k["birthday"] == "1990-03-07"
        assert "8613812345678" in k["phone"]
        assert "北京" in k["address"]
        assert out["unmasked"] is True

    async def test_unknown_audit_status(self, fake_db) -> None:
        fake_db.row = {
            "audit_status": 99, "identity_failer_reason": None,
            "certification_status": 0, "country_area": None,
            "live_country": None, "identity_card_type": None,
            "first_name": None, "last_name": None,
            "identity_card": None, "birthday": None,
            "phone_code": None, "phone_number": None,
            "address": None, "city": None, "post_code": None,
            "request_time": None, "audit_pass_time": None,
            "user_kyc_status": 99,
        }
        out = await qk.run(user_id="1")
        k = out["kyc"]
        assert k["audit_status"] == "未知(99)"
        assert k["user_kyc_status"] == "未知(99)"

    async def test_note_mentions_authority(self, fake_db) -> None:
        fake_db.row = {
            "audit_status": 1, "identity_failer_reason": None,
            "certification_status": 1, "country_area": None,
            "live_country": None, "identity_card_type": None,
            "first_name": None, "last_name": None,
            "identity_card": None, "birthday": None,
            "phone_code": None, "phone_number": None,
            "address": None, "city": None, "post_code": None,
            "request_time": None, "audit_pass_time": None,
            "user_kyc_status": 0,
        }
        out = await qk.run(user_id="1")
        # note 提示以 user_kyc_status 为准
        assert "user_kyc_status" in out["note"]
        assert "权威" in out["note"]
