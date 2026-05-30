import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:00:00'), "
        "(1, 'AG1', 'resolved', '2026-05-30 00:05:00')"
    )
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "ag": issue_staff_token("AG1", "agent"),
    }
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/staff/AG1/performance", headers=_h(env["ag"]))
    assert r.status_code == 403


async def test_sup_performance(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/staff/AG1/performance", headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert body["staff_id"] == "AG1"
    assert body["takeovers"] == 1
    assert "satisfaction" in body and "qa" in body
