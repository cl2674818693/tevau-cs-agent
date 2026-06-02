"""API: GET /staff/api/v1/conversations/{id}/subject-info（staff_subject_info.py，新功能）。

被测对象：admin/客服详情页 InfoCard 一次性聚合：用户基本信息 + 近 30 天交易 + 客户端环境。
两路分支：
- user_type='c'：t_tevaupay_user + t_tevaupay_card_recharge_records
- user_type='b'：t_nexus_company_info

mock 策略：
- 业务库整体未配置（默认）→ get_db raise → 端点 try/except 兜底，subject.found=False
- mock get_db.fetch_one/fetch_all 模拟各种 row 形态（命中 / 不命中 / 抛错）
- client_info 通过真实 sqlite client_info 表写入

异常矩阵（题面 6 条）：
1. 普通客服调 → 200
2. 未登录 → 401
3. conversation 不存在 → 404
4. subject_id 不存在于业务库 → 200，subject.found=False
5. 业务库连接失败 → 200，subject.found=False（端点优雅降级，不 502/503）
6. client_info 命中 → 200，返回 client_info 对象
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_subject_info import router as staff_subject_info_router
from ai_engine.persistence import client_info as ci_dao

from .conftest import insert_conversation


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_subject_info_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _patch_business_db(
    monkeypatch, *, fetch_one_row: Any = None, fetch_all_rows: Any = None
) -> MagicMock:
    """让 staff_subject_info 模块里 import 的 get_db 返回 mock DB。"""
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value=fetch_one_row)
    mock_db.fetch_all = AsyncMock(return_value=(fetch_all_rows or []))
    mock_get_db = MagicMock(return_value=mock_db)
    monkeypatch.setattr("ai_engine.api.staff_subject_info.get_db", mock_get_db)
    return mock_get_db


class TestSubjectInfoAuth:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        cid = await insert_conversation()
        resp = await client.get(f"/staff/api/v1/conversations/{cid}/subject-info")
        assert resp.status_code == 401

    async def test_bad_token_401(self, init_self_db, client) -> None:
        cid = await insert_conversation()
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401


class TestSubjectInfoConversationNotFound:
    async def test_unknown_conv_404(self, init_self_db, client, agent_headers) -> None:
        resp = await client.get(
            "/staff/api/v1/conversations/99999/subject-info", headers=agent_headers
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


class TestSubjectInfoCSide:
    """user_type='c' 分支：查 t_tevaupay_user + 30 天交易聚合。"""

    async def test_c_user_found_with_transactions(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="100")

        # _c_subject_info 内部先 fetch_one(_C_USER_SQL)，再 fetch_all(_C_TX_AGG_SQL)
        # _b_subject_info 也用 get_db.fetch_one；本例只走 c 分支。
        _patch_business_db(
            monkeypatch,
            fetch_one_row={
                "id": 100,
                "user_code": "C0001",
                "email_address": "alice@x.com",
                "mobile_phone": "13800000000",
                "nick_name": "Alice",
                "user_status": 0,
                "kyc_status": 1,
                "open_card_status": 1,
                "registration_time": "2026-01-01 10:00:00",
                "last_login_time": "2026-05-01 09:00:00",
            },
            fetch_all_rows=[
                {"currency": 1, "cnt": 3, "amt": "150.50"},
                {"currency": 2, "cnt": 2, "amt": "20"},
            ],
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        sub = body["subject"]
        assert sub["user_type"] == "c"
        assert sub["found"] is True
        assert sub["user_id"] == 100
        assert sub["user_code"] == "C0001"
        assert sub["email"] == "alice@x.com"
        assert sub["user_status"] == "正常"
        assert sub["kyc_status"] == "已认证"
        assert sub["open_card_status"] == "已开卡"
        # 交易：currency 1=USDT，2=USD
        txs = sub["recent_30d_transactions"]
        assert len(txs) == 2
        assert txs[0]["currency"] == "USDT"
        assert txs[0]["count"] == 3
        assert txs[1]["currency"] == "USD"

    async def test_c_user_not_found(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        """subject_id 在业务库无行 → fetch_one None → subject.found=False。"""
        cid = await insert_conversation(user_type="c", subject_id="999")
        _patch_business_db(monkeypatch, fetch_one_row=None, fetch_all_rows=[])
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json()["subject"]["found"] is False
        assert resp.json()["subject"]["user_type"] == "c"

    async def test_c_user_no_transactions(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="100")
        _patch_business_db(
            monkeypatch,
            fetch_one_row={
                "id": 100, "user_code": "C0001", "email_address": None,
                "mobile_phone": None, "nick_name": None, "user_status": 0,
                "kyc_status": 0, "open_card_status": 0,
                "registration_time": None, "last_login_time": None,
            },
            fetch_all_rows=[],
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        sub = resp.json()["subject"]
        assert sub["found"] is True
        assert sub["recent_30d_transactions"] == []
        assert sub["registration_time"] is None

    async def test_unknown_currency_passthrough(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        """新币种编码 → label table 未命中 → 回退到 str(currency)。"""
        cid = await insert_conversation(user_type="c", subject_id="100")
        _patch_business_db(
            monkeypatch,
            fetch_one_row={
                "id": 100, "user_code": "C", "email_address": None,
                "mobile_phone": None, "nick_name": None, "user_status": None,
                "kyc_status": None, "open_card_status": None,
                "registration_time": None, "last_login_time": None,
            },
            fetch_all_rows=[{"currency": 999, "cnt": 1, "amt": "1"}],
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json()["subject"]["recent_30d_transactions"][0]["currency"] == "999"


class TestSubjectInfoBSide:
    """user_type='b' 分支：查 t_nexus_company_info。"""

    async def test_b_company_found(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        _patch_business_db(
            monkeypatch,
            fetch_one_row={
                "tenant_id": "1011010000068",
                "company_name": "示例租户",
                "status": 1,
            },
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        sub = resp.json()["subject"]
        assert sub["user_type"] == "b"
        assert sub["found"] is True
        assert sub["company_name"] == "示例租户"
        assert sub["status"] == "运行中"

    async def test_b_company_disabled(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="X")
        _patch_business_db(
            monkeypatch,
            fetch_one_row={
                "tenant_id": "X", "company_name": "Off", "status": 2
            },
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json()["subject"]["status"] == "已停用"

    async def test_b_company_not_found(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="GHOST")
        _patch_business_db(monkeypatch, fetch_one_row=None)
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        sub = resp.json()["subject"]
        assert sub["found"] is False
        assert sub["user_type"] == "b"


class TestSubjectInfoBusinessDbFailure:
    """业务库连接失败 / SQL 抛错 → 端点优雅降级返回 found=False（不 502/503）。"""

    async def test_business_db_not_initialized(
        self, init_self_db, client, agent_headers
    ) -> None:
        """业务库未配置 → get_db 抛 RuntimeError → try/except 兜底。"""
        cid = await insert_conversation(user_type="c", subject_id="100")
        # 不 patch get_db，让真实的 get_db 抛 "business db not initialized"
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        sub = resp.json()["subject"]
        assert sub["found"] is False
        assert sub["user_type"] == "c"
        assert sub["subject_id"] == "100"

    async def test_business_db_fetch_throws(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        mock_db = MagicMock()
        mock_db.fetch_one = AsyncMock(side_effect=ConnectionError("mysql down"))
        monkeypatch.setattr(
            "ai_engine.api.staff_subject_info.get_db",
            MagicMock(return_value=mock_db),
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        # 端点 try/except 把异常吃掉，返回 200 + found=False（spec 优雅降级）
        assert resp.status_code == 200
        assert resp.json()["subject"]["found"] is False


class TestSubjectInfoClientInfo:
    async def test_client_info_returned_when_present(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="100")
        await ci_dao.upsert_client_info(
            cid, platform="ios", app_version="3.4.5", user_agent="Tevau iOS"
        )
        _patch_business_db(monkeypatch, fetch_one_row=None)
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        ci = resp.json()["client_info"]
        assert ci["platform"] == "ios"
        assert ci["app_version"] == "3.4.5"
        assert ci["user_agent"] == "Tevau iOS"

    async def test_client_info_null_when_absent(
        self, init_self_db, client, agent_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="100")
        _patch_business_db(monkeypatch, fetch_one_row=None)
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/subject-info", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json()["client_info"] is None

    async def test_role_open_to_all_staff(
        self, init_self_db, client, monkeypatch, auth_headers
    ) -> None:
        """端点只 require_staff，不限角色：agent/senior/engineer/admin 都能调。"""
        cid = await insert_conversation(user_type="c", subject_id="100")
        _patch_business_db(monkeypatch, fetch_one_row=None)
        for role in ("agent", "senior", "engineer", "admin", "supervisor", "manager"):
            resp = await client.get(
                f"/staff/api/v1/conversations/{cid}/subject-info",
                headers=auth_headers(role),
            )
            assert resp.status_code == 200, f"role {role} should be allowed"
