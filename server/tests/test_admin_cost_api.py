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

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO daily_token_usage(subject_id, user_type, date, "
        "input_tokens, output_tokens, model) VALUES "
        "('u1', 'b', '2026-05-30', 1000, 500, 'claude-sonnet-4-6')"
    )
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
        "ag": issue_staff_token("AG1", "agent"),
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
        r = await c.get("/admin/api/v1/cost/usage", headers=_h(env["ag"]))
    assert r.status_code == 403


async def test_usage_by_model(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/cost/usage?with_cost=true", headers=_h(env["eng"]))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["model"] == "claude-sonnet-4-6" for i in items)


async def test_pricing_crud(env):
    from ai_engine.persistence import admin_audit

    async with await _c() as c:
        r = await c.put(
            "/admin/api/v1/cost/pricing",
            json={
                "model": "claude-sonnet-4-6",
                "input_price_per_1k_x10000": 30000,
                "output_price_per_1k_x10000": 150000,
                "currency": "USD",
            },
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        listed = (await c.get("/admin/api/v1/cost/pricing", headers=_h(env["eng"]))).json()[
            "items"
        ]
    assert any(p["model"] == "claude-sonnet-4-6" for p in listed)
    audits = await admin_audit.list_admin_actions(action="cost.pricing.upsert", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)
