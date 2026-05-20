import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _clear_rate():
    from ai_engine.api.auth_bu import _RATE_BUCKET

    _RATE_BUCKET.clear()
    yield
    _RATE_BUCKET.clear()


async def test_login_valid_bu_sets_cookie(business_mysql):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU00243780"})
    assert r.status_code == 200
    assert "ai_engine_session" in r.headers.get("set-cookie", "")


async def test_login_invalid_bu_returns_generic_error(business_mysql):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU999999"})
    assert r.status_code == 401
    assert "主账户不存在或已禁用" in r.text


async def test_login_rate_limit(business_mysql):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for _ in range(5):
            await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU000000"})
        r = await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU000000"})
    assert r.status_code == 429


async def test_chat_requires_session():
    """无 cookie / 无 X-BU-ID 调 /chat → 401。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/api/v1/chat?conversation_id=1&message=hi")
    assert r.status_code == 401


async def test_login_then_cookie_authorizes(temp_db_url, business_mysql):
    """登录拿 cookie → 用 cookie 调会话初始化成功。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence.db import init_db

    await init_db()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post("/api/v1/auth/bu/login", json={"bu_id": "BU00243780"})
        # httpx 客户端自动带回 Set-Cookie
        r = await client.post("/api/v1/conversations", json={})
    assert r.status_code == 200
    assert r.json()["user_type"] == "b"
