from httpx import ASGITransport, AsyncClient


async def _setup_staff(monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-secret")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff

    await init_db()
    await create_staff("S100", "张三", "agent", "secret123")


async def test_staff_login_success(temp_db_url, monkeypatch):
    await _setup_staff(monkeypatch)
    from ai_engine import main as main_mod
    from ai_engine.auth.staff_session import verify_staff_token

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/staff/api/v1/auth/login", json={"staff_id": "S100", "password": "secret123"}
        )
    assert r.status_code == 200
    data = r.json()
    assert data["staff"]["display_name"] == "张三"
    claims = verify_staff_token(data["token"])
    assert claims["sub"] == "S100" and claims["role"] == "agent" and claims["typ"] == "staff"


async def test_staff_login_wrong_password(temp_db_url, monkeypatch):
    await _setup_staff(monkeypatch)
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/staff/api/v1/auth/login", json={"staff_id": "S100", "password": "WRONG"}
        )
    assert r.status_code == 401


async def test_require_staff_rejects_non_staff_token(monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-secret")
    from ai_engine.config import settings

    settings.reload()
    import jwt as _jwt
    import pytest

    from ai_engine.auth.staff_session import verify_staff_token

    bad = _jwt.encode({"typ": "user", "sub": "x"}, "test-secret", algorithm="HS256")
    with pytest.raises(ValueError):
        verify_staff_token(bad)
