import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import guardrails
    from ai_engine.persistence.staff import create_staff

    guardrails.invalidate_cache()
    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    guardrails.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/guardrails", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_crud(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/guardrails",
            json={"type": "sensitive_word", "pattern": "敏感词", "action": "flag"},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/guardrails", headers=_h(env["eng"]))).json()["rules"]
        assert any(g["id"] == rid for g in listed)
        await c.patch(f"/admin/api/v1/guardrails/{rid}",
                      json={"active": 0}, headers=_h(env["eng"]))
        await c.delete(f"/admin/api/v1/guardrails/{rid}", headers=_h(env["eng"]))


async def test_create_bad_type_400(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/guardrails",
            json={"type": "bogus", "pattern": "x", "action": "block"},
            headers=_h(env["eng"]),
        )
    assert r.status_code == 400
