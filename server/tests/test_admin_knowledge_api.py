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
        r = await c.get("/admin/api/v1/knowledge", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_publish_list(env):
    from ai_engine.persistence import admin_audit
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/knowledge",
            json={"type": "faq", "key": "login", "title": "登录指南",
                  "content": "怎么登录...", "locale": "zh"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        eid = r.json()["id"]
        pub = await c.post(f"/admin/api/v1/knowledge/{eid}/publish", headers=_h(env["sup"]))
        assert pub.status_code == 200
        listed = (await c.get("/admin/api/v1/knowledge?type=faq",
                              headers=_h(env["sup"]))).json()["entries"]
    assert any(e["id"] == eid and e["status"] == "published" for e in listed)
    audits = await admin_audit.list_admin_actions(action="knowledge.publish", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)


async def test_from_gap_endpoint(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/knowledge/from-gap",
            json={"signal_key": "out_of_scope:卡片申请",
                  "type": "faq", "key": "card_apply", "title": "卡片申请说明",
                  "content": "..."},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        eid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/knowledge?type=faq",
                              headers=_h(env["sup"]))).json()["entries"]
    target = next((e for e in listed if e["id"] == eid), None)
    assert target is not None
    assert target["source_gap_signal"] == "out_of_scope:卡片申请"
