import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import admin_audit
    from ai_engine.persistence.staff import create_staff

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await admin_audit.log_admin_action(actor="AD1", action="staff.create", target_id="X1")
    yield {"eng": issue_staff_token("EN1", "engineer"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_engineer_can_list(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit", headers=_h(env["eng"]))
    assert r.status_code == 200
    assert any(e["action"] == "staff.create" for e in r.json()["entries"])


async def test_filter_by_action(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/audit?action=sla.update", headers=_h(env["eng"]))
    assert r.status_code == 200
    assert r.json()["entries"] == []
