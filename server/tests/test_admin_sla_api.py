import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/sla/policies", headers=_h(env["agent"]))
        assert r.status_code == 403


async def test_create_list_policy(env):
    async with await _c() as c:
        r = await c.post("/admin/api/v1/sla/policies",
                         json={"metric": "take_time", "threshold_seconds": 300, "scope": "all"},
                         headers=_h(env["sup"]))
        assert r.status_code == 200
        resp = await c.get("/admin/api/v1/sla/policies", headers=_h(env["sup"]))
        listed = resp.json()["policies"]
    assert any(p["metric"] == "take_time" for p in listed)


async def test_breaches_endpoint(env):
    from ai_engine.persistence import db
    await db.execute(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES ('c','u1','human_pending','2000-01-01 00:00:00')"
    )
    async with await _c() as c:
        await c.post("/admin/api/v1/sla/policies",
                     json={"metric": "take_time", "threshold_seconds": 60, "scope": "all"},
                     headers=_h(env["sup"]))
        r = await c.get("/admin/api/v1/sla/breaches", headers=_h(env["sup"]))
    assert r.status_code == 200
    assert any(b["metric"] == "take_time" for b in r.json()["breaches"])
