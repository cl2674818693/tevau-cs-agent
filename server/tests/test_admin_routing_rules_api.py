import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import routing_rules
    from ai_engine.persistence.staff import create_staff

    routing_rules.invalidate_cache()
    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    routing_rules.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/routing-rules", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_set_active_delete(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/routing-rules",
            json={"match_type": "user_type", "match_value": "c",
                  "target_group_id": 1, "priority": 10},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/routing-rules",
                              headers=_h(env["sup"]))).json()["rules"]
        assert any(rr["id"] == rid for rr in listed)
        await c.patch(f"/admin/api/v1/routing-rules/{rid}",
                      json={"active": 0}, headers=_h(env["sup"]))
        await c.delete(f"/admin/api/v1/routing-rules/{rid}", headers=_h(env["sup"]))
        listed_after = (await c.get("/admin/api/v1/routing-rules",
                                    headers=_h(env["sup"]))).json()["rules"]
        assert all(rr["id"] != rid for rr in listed_after)
    audits = await admin_audit.list_admin_actions(action="routing_rule.create", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)


async def test_create_bad_match_type_400(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/routing-rules",
            json={"match_type": "bogus", "match_value": "x",
                  "target_group_id": 1, "priority": 10},
            headers=_h(env["sup"]),
        )
    assert r.status_code == 400
