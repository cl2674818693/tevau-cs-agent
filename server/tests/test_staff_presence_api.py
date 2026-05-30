import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("SUP1", "主管", "supervisor", "x")
    yield {
        "agent": issue_staff_token("AG1", "agent"),
        "sup": issue_staff_token("SUP1", "supervisor"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_heartbeat_self(env):
    async with await _c() as c:
        r = await c.post("/staff/api/v1/presence", json={"status": "online"},
                         headers=_h(env["agent"]))
    assert r.status_code == 200


async def test_admin_list_presence(env):
    async with await _c() as c:
        await c.post("/staff/api/v1/presence", json={"status": "online"},
                     headers=_h(env["agent"]))
        r = await c.get("/admin/api/v1/presence", headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert any(p["staff_id"] == "AG1" and p["status"] == "online" for p in body["all"])
    assert "active" in body


async def test_admin_list_forbidden_for_agent(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/presence", headers=_h(env["agent"]))
    assert r.status_code == 403
