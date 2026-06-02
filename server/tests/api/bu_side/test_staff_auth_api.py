"""API: /staff/api/v1/auth/login（staff_auth.py）。

被测对象：客服登录 → 校验账号/密码 → 签发 staff JWT。
mock 策略：真实 sqlite 自有库 + `init_self_db` 建表，直接 INSERT 一条 staff，验真实 PBKDF2 流程。

异常矩阵：
1. happy path → 200 + 合法 JWT
2. 密码错 → 401
3. 账号不存在 → 401
4. 账号 active=0 → 401
5. body 缺字段 → 422
6. 空 STAFF_JWT_SECRET → 500（issue 抛 RuntimeError）
7. 签出 token 用 verify_staff_token 能解，role/sub 正确
"""

from collections.abc import AsyncIterator

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_auth import router as staff_auth_router
from ai_engine.auth.staff_session import verify_staff_token

from .conftest import insert_staff


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_auth_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestStaffLoginHappyPath:
    async def test_login_with_correct_credentials(self, init_self_db, client) -> None:
        await insert_staff("agent-1", "Agent One", "agent", "p@ssw0rd")
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "agent-1", "password": "p@ssw0rd"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "token" in body
        assert body["staff"] == {
            "staff_id": "agent-1",
            "display_name": "Agent One",
            "role": "agent",
        }

    async def test_issued_token_verifies(self, init_self_db, client) -> None:
        """签出的 token 用 verify_staff_token 能解出 sub/role/typ。"""
        await insert_staff("eng-9", "Engineer", "engineer", "secret-pw-9")
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "eng-9", "password": "secret-pw-9"},
        )
        token = resp.json()["token"]
        claims = verify_staff_token(token)
        assert claims["sub"] == "eng-9"
        assert claims["role"] == "engineer"
        assert claims["typ"] == "staff"

    @pytest.mark.parametrize("role", ["agent", "senior", "engineer", "admin", "supervisor", "manager"])
    async def test_login_supports_all_valid_roles(self, init_self_db, client, role: str) -> None:
        await insert_staff(f"{role}-x", f"{role} disp", role, "pw-xx")
        resp = await client.post(
            "/staff/api/v1/auth/login", json={"staff_id": f"{role}-x", "password": "pw-xx"}
        )
        assert resp.status_code == 200
        assert resp.json()["staff"]["role"] == role


class TestStaffLoginRejected:
    async def test_login_wrong_password_returns_401(self, init_self_db, client) -> None:
        await insert_staff("agent-2", "A2", "agent", "right-pw")
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "agent-2", "password": "wrong-pw"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    async def test_login_unknown_staff_returns_401(self, init_self_db, client) -> None:
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "nobody", "password": "x"},
        )
        assert resp.status_code == 401

    async def test_login_inactive_staff_returns_401(self, init_self_db, client) -> None:
        await insert_staff("agent-x", "X", "agent", "pw-xx", active=0)
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "agent-x", "password": "pw-xx"},
        )
        assert resp.status_code == 401


class TestStaffLoginValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            {},
            {"staff_id": "x"},  # 缺密码
            {"password": "x"},  # 缺账号
        ],
    )
    async def test_invalid_body_returns_422(self, init_self_db, client, bad: dict) -> None:
        resp = await client.post("/staff/api/v1/auth/login", json=bad)
        assert resp.status_code == 422


class TestStaffLoginSecretMissing:
    """STAFF_JWT_SECRET 空时端点显式返 503（服务未就绪），不再让 issue_staff_token 裸抛 500。
    防止空密钥下 HS256 空串签名被攻击者伪造 admin token 的旁路也覆盖在 issue_staff_token 自身。
    """

    async def test_login_without_secret_returns_503(
        self, init_self_db, client, monkeypatch
    ) -> None:
        from ai_engine.config import settings

        monkeypatch.setenv("STAFF_JWT_SECRET", "")
        settings.reload()
        await insert_staff("agent-z", "Z", "agent", "pw-zz")
        resp = await client.post(
            "/staff/api/v1/auth/login",
            json={"staff_id": "agent-z", "password": "pw-zz"},
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]


class TestVerifyStaffTokenRejection:
    """额外覆盖：非 staff typ 的 token 应被 require_staff 拒。"""

    async def test_token_with_wrong_typ_rejected(self, _staff_jwt_env) -> None:
        from ai_engine.auth.staff_session import verify_staff_token
        from ai_engine.config import settings

        # 自己用项目当前签名密钥签一个 typ=b 的 token —— 验签通过但 typ 不对
        bogus = jwt.encode(
            {"typ": "b", "sub": "fake"}, settings.staff_jwt_secret, algorithm="HS256"
        )
        with pytest.raises(ValueError, match="not staff"):
            verify_staff_token(bogus)
