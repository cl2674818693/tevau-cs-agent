import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("MGR1", "老板", "manager", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {"mgr": issue_staff_token("MGR1", "manager"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_agent_forbidden(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/dashboard/overview", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_manager_overview_shape(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get("/admin/api/v1/dashboard/overview", headers=_h(env["mgr"]))
    assert r.status_code == 200
    body = r.json()
    for k in ("total_conversations", "handoff_rate", "downvote_rate", "tool_empty_rate",
              "out_of_scope", "failed_turns"):
        assert k in body
