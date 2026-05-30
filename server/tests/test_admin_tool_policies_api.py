import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import tool_policies
    from ai_engine.persistence.staff import create_staff

    tool_policies.invalidate_cache()

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
        "ag": issue_staff_token("AG1", "agent"),
    }
    tool_policies.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod

    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_agent_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/tool-policies", headers=_h(env["ag"]))
    assert r.status_code == 403


async def test_engineer_list_and_upsert(env):
    from ai_engine.persistence import admin_audit

    async with await _c() as c:
        r0 = await c.get("/admin/api/v1/tool-policies", headers=_h(env["eng"]))
        assert r0.status_code == 200
        r = await c.put(
            "/admin/api/v1/tool-policies",
            json={
                "items": [
                    {
                        "tool_name": "query_user",
                        "role": "senior",
                        "allowed": 1,
                        "unmask_allowed": 1,
                    }
                ]
            },
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        listed = (
            await c.get("/admin/api/v1/tool-policies", headers=_h(env["eng"]))
        ).json()["items"]
    assert any(
        i["tool_name"] == "query_user" and i["role"] == "senior" and int(i["unmask_allowed"]) == 1
        for i in listed
    )
    audits = await admin_audit.list_admin_actions(action="tool_policies.upsert", limit=10)
    assert any(a["actor"] == "EN1" for a in audits)
