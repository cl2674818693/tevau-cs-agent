import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff
    from ai_engine.persistence.tickets import append_ticket_event, create_ticket

    await create_staff("AG1", "客服", "agent", "x")
    await create_ticket("T-1", 1, {"category": "billing", "severity": "high"})
    await append_ticket_event("T-1", "in_progress", actor="op1", comment="受理")
    yield {"agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_get_ticket_detail(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/T-1", headers=_h(env["agent"]))
    assert r.status_code == 200
    body = r.json()
    assert body["external_id"] == "T-1"
    assert len(body["events"]) == 1
    assert body["events"][0]["event"] == "in_progress"


async def test_get_ticket_404(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/NOPE", headers=_h(env["agent"]))
    assert r.status_code == 404


async def test_get_ticket_needs_auth(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/staff/api/v1/tickets/T-1")
    assert r.status_code == 401
