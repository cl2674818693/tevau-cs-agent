"""API: /api/v1/auth/bu/login + /logout（auth_bu.py）。

被测对象：B 端主账户登录—— 查 nexus.t_nexus_company_info 验账号，签发 HS256 cookie。
mock 策略：
- 默认不依赖业务库：用 monkeypatch 替换 `business_db.get_db` 的 `fetch_one`，
  返回构造好的 row（active/已停用/不存在）。
- 速率限制（5 次/60s）：直接清掉 _RATE_BUCKET 做边界测试。
- happy-path 真业务库的版本走 `business_mysql` fixture（无 docker 时 skip）。

异常矩阵：
1. happy path → 200 + cookie
2. 账号不存在 → 401
3. 账号 status=2(停用) → 401
4. 参数非法（含特殊字符 / 太短 / 空）→ 422
5. 速率限制超限 → 429
6. logout 清 cookie → 200
"""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.auth_bu import _RATE_BUCKET
from ai_engine.api.auth_bu import router as auth_bu_router
from ai_engine.auth.bu_session import SESSION_COOKIE, _verify_bu_session


@pytest.fixture(autouse=True)
def _reset_rate_bucket() -> None:
    """每个 case 跑前清空进程内速率窗口，避免相互污染。"""
    _RATE_BUCKET.clear()
    yield
    _RATE_BUCKET.clear()


@pytest.fixture
def bu_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_bu_router)
    return app


@pytest.fixture
async def client(bu_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=bu_app), base_url="http://test") as ac:
        yield ac


def _mock_get_db(monkeypatch, *, row: dict[str, Any] | None) -> MagicMock:
    """让 auth_bu 模块里 import 的 get_db 返回一个 mock db，fetch_one 给指定 row。"""
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value=row)
    mock_get_db = MagicMock(return_value=mock_db)
    monkeypatch.setattr("ai_engine.api.auth_bu.get_db", mock_get_db)
    return mock_get_db


class TestBuLoginHappyPath:
    """正常登录：账号存在 + status != 2 → 200 + 设 HttpOnly cookie。"""

    async def test_login_with_active_tenant(self, client, monkeypatch) -> None:
        _mock_get_db(monkeypatch, row={"tenant_id": "1011010000068", "status": 1})
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "1011010000068"})
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"ok": True, "bu_id": "1011010000068"}
        # cookie 已设
        cookie = resp.cookies.get(SESSION_COOKIE)
        assert cookie is not None
        # 验签能解出原 tenant_id
        assert _verify_bu_session(cookie) == "1011010000068"

    async def test_login_with_pending_tenant_status_0(self, client, monkeypatch) -> None:
        """status=0（待开启）也允许登录；只拒 status=2。"""
        _mock_get_db(monkeypatch, row={"tenant_id": "T0", "status": 0})
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "T0"})
        assert resp.status_code == 200

    async def test_login_with_null_status_treated_as_zero(self, client, monkeypatch) -> None:
        """status=None → int(0) → 允许登录（防止历史脏数据被一刀切。)"""
        _mock_get_db(monkeypatch, row={"tenant_id": "T1", "status": None})
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "T1"})
        assert resp.status_code == 200


class TestBuLoginRejected:
    """账号不存在 / 停用 / 删除 — 统一返回 401（防枚举）。"""

    async def test_login_unknown_tenant_returns_401(self, client, monkeypatch) -> None:
        _mock_get_db(monkeypatch, row=None)  # SELECT 无行
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "NOPE0000"})
        assert resp.status_code == 401
        assert "主账户" in resp.json()["detail"] or "不存在" in resp.json()["detail"]

    async def test_login_disabled_tenant_status_2_returns_401(self, client, monkeypatch) -> None:
        _mock_get_db(monkeypatch, row={"tenant_id": "X", "status": 2})
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "X"})
        assert resp.status_code == 401

    async def test_login_rejected_does_not_set_cookie(self, client, monkeypatch) -> None:
        _mock_get_db(monkeypatch, row=None)
        resp = await client.post("/api/v1/auth/bu/login", json={"bu_id": "NOPE"})
        assert resp.status_code == 401
        assert resp.cookies.get(SESSION_COOKIE) is None


class TestBuLoginValidation:
    """参数校验 (pydantic) — 422 不进 DB。"""

    @pytest.mark.parametrize(
        "bad",
        [
            {},  # 缺字段
            {"bu_id": ""},  # 长度 0
            {"bu_id": "a" * 33},  # > max_length 32
            {"bu_id": "bad-id"},  # 含 "-" 不在 [A-Za-z0-9]
            {"bu_id": "bu id"},  # 含空格
            {"bu_id": "中文ID"},  # 非 ASCII
            {"bu_id": 12345},  # 类型错（数字非字符串）
        ],
    )
    async def test_invalid_payload_returns_422(self, client, monkeypatch, bad: dict) -> None:
        # mock get_db 防止真去查 DB
        _mock_get_db(monkeypatch, row=None)
        resp = await client.post("/api/v1/auth/bu/login", json=bad)
        assert resp.status_code == 422


class TestBuLoginRateLimit:
    """5 次/60s 速率限制：第 6 次同 IP 应 429（注：mock client.host 全部为 "testclient"）。"""

    async def test_rate_limit_blocks_after_5_attempts(self, client, monkeypatch) -> None:
        _mock_get_db(monkeypatch, row=None)  # 让登录都 401，触发 5 次窗口
        for _ in range(5):
            r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "X"})
            assert r.status_code == 401
        # 第 6 次：rate_limit 应在校验账号前拒掉
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "X"})
        assert r.status_code == 429
        assert "too many" in r.json()["detail"]

    async def test_rate_limit_isolated_after_reset(self, client, monkeypatch) -> None:
        """reset _RATE_BUCKET 后允许重新登录。autouse 已 reset，本例只验证可登。"""
        _mock_get_db(monkeypatch, row={"tenant_id": "Y", "status": 1})
        for _ in range(5):  # 5 次都成功 → 不超限
            r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "Y"})
            assert r.status_code == 200


class TestBuLogout:
    """logout 不依赖鉴权（前端调用时可能 cookie 已过期），统一 200 + 清 cookie。"""

    async def test_logout_clears_cookie(self, client) -> None:
        resp = await client.post("/api/v1/auth/bu/logout")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        # Set-Cookie 含 ai_engine_session= 的清除指令；max-age=0 或空值
        set_cookie_hdrs = resp.headers.get_list("set-cookie")
        assert any(SESSION_COOKIE in h for h in set_cookie_hdrs)


class TestBuLoginRealMysql:
    """端到端：真业务 MySQL（无 docker 时 skip）。"""

    async def test_login_real_seeded_tenant(self, business_mysql, client) -> None:
        # unlimitpay_seed.sql 已插入 tenant_id=1011010000068 status=1
        resp = await client.post(
            "/api/v1/auth/bu/login", json={"bu_id": "1011010000068"}
        )
        assert resp.status_code == 200
        assert resp.cookies.get(SESSION_COOKIE) is not None

    async def test_login_real_disabled_tenant_401(self, business_mysql, client) -> None:
        # tenant_id=1011010000999 status=2
        resp = await client.post(
            "/api/v1/auth/bu/login", json={"bu_id": "1011010000999"}
        )
        assert resp.status_code == 401
