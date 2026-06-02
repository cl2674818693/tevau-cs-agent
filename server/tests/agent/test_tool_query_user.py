"""Tool: query_user

被测对象：tools.query_user.run
- 命中：脱敏邮箱/手机、枚举翻译（user_status / kyc_status / open_card_status）。
- 未命中：{user: None, note}。
- unmask=True：邮箱/手机原值返回。
- 未知枚举值 → label() 标注 未知(原值)。

mock 策略：把 get_db('unlimitpay') 替换成内存假 DB。
"""

import pytest

from ai_engine.agent.tools import query_user as qu
from ai_engine.persistence import business_db as bdb


class _FakeDB:
    def __init__(self, row: dict | None = None) -> None:
        self.row = row

    async def fetch_one(self, _sql, _params):
        return self.row

    async def fetch_all(self, *_a, **_k):  # noqa: ANN002,ANN003
        return []


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeDB()

    def _get(name: str):
        assert name == "unlimitpay"
        return fake

    monkeypatch.setattr(bdb, "get_db", _get)
    monkeypatch.setattr(qu, "get_db", _get, raising=False)
    return fake


class TestQueryUser:
    async def test_user_not_found(self, fake_db) -> None:
        out = await qu.run(user_id="999")
        assert out["user"] is None
        assert "not found" in out["note"]

    async def test_user_masked_by_default(self, fake_db) -> None:
        fake_db.row = {
            "id": 1,
            "user_code": "U1",
            "email_address": "alice@example.com",
            "mobile_phone": "13812345678",
            "nick_name": "Alice",
            "user_status": 0,
            "kyc_status": 1,
            "open_card_status": 0,
            "registration_time": None,
            "last_login_time": None,
        }
        out = await qu.run(user_id="1")
        u = out["user"]
        assert u["email"] != "alice@example.com"
        assert "@example.com" in u["email"]
        assert u["phone"] != "13812345678"
        # 枚举翻译
        assert u["user_status"] == "正常"
        assert u["kyc_status"] == "已认证"
        assert u["open_card_status"] == "未开卡"
        assert out["unmasked"] is False

    async def test_unmask_true_returns_plaintext(self, fake_db) -> None:
        fake_db.row = {
            "id": 1,
            "user_code": "U1",
            "email_address": "bob@x.com",
            "mobile_phone": "13911112222",
            "nick_name": "B",
            "user_status": 0,
            "kyc_status": 0,
            "open_card_status": 1,
            "registration_time": None,
            "last_login_time": None,
        }
        out = await qu.run(user_id="1", unmask=True)
        u = out["user"]
        assert u["email"] == "bob@x.com"
        assert u["phone"] == "13911112222"
        assert out["unmasked"] is True

    async def test_unknown_status_labels_with_raw(self, fake_db) -> None:
        fake_db.row = {
            "id": 2,
            "user_code": "U2",
            "email_address": None,
            "mobile_phone": None,
            "nick_name": None,
            "user_status": 99,  # 字典外
            "kyc_status": 7,    # 字典外
            "open_card_status": None,
            "registration_time": None,
            "last_login_time": None,
        }
        out = await qu.run(user_id="2")
        u = out["user"]
        assert u["user_status"] == "未知(99)"
        assert u["kyc_status"] == "未知(7)"
        assert u["open_card_status"] is None  # None → label 返回 None

    async def test_time_fields_stringified(self, fake_db) -> None:
        fake_db.row = {
            "id": 1,
            "user_code": "U1",
            "email_address": None,
            "mobile_phone": None,
            "nick_name": None,
            "user_status": 0,
            "kyc_status": 0,
            "open_card_status": 0,
            "registration_time": "2026-01-01 00:00:00",
            "last_login_time": None,
        }
        out = await qu.run(user_id="1")
        assert out["user"]["registration_time"] == "2026-01-01 00:00:00"
        assert out["user"]["last_login_time"] is None

    async def test_upstream_exception_propagates(self, monkeypatch) -> None:
        class _Boom(_FakeDB):
            async def fetch_one(self, _sql, _params):
                raise RuntimeError("db down")

        fake = _Boom()
        monkeypatch.setattr(qu, "get_db", lambda _n: fake, raising=False)
        with pytest.raises(RuntimeError, match="db down"):
            await qu.run(user_id="1")
