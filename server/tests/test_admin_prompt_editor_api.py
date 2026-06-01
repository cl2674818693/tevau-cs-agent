import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("EN1", "工程", "engineer", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "eng": issue_staff_token("EN1", "engineer"),
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
        r = await c.get("/admin/api/v1/prompt-editor?version=v1.0.0",
                        headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_publish_get(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/prompt-editor",
            json={"version": "v2.0.0", "file_name": "a.md", "content": "草稿内容"},
            headers=_h(env["eng"]),
        )
        assert r.status_code == 200
        did = r.json()["id"]
        pub = await c.post(
            f"/admin/api/v1/prompt-editor/{did}/publish",
            headers=_h(env["eng"]),
        )
        assert pub.status_code == 200
        listed = (await c.get("/admin/api/v1/prompt-editor?version=v2.0.0",
                              headers=_h(env["eng"]))).json()["drafts"]
    assert any(d["id"] == did and d["status"] == "published" for d in listed)


async def test_delete_draft(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/prompt-editor",
            json={"version": "v2.0.0", "file_name": "b.md", "content": "x"},
            headers=_h(env["eng"]),
        )
        did = r.json()["id"]
        await c.delete(f"/admin/api/v1/prompt-editor/{did}", headers=_h(env["eng"]))
        listed = (await c.get("/admin/api/v1/prompt-editor?version=v2.0.0",
                              headers=_h(env["eng"]))).json()["drafts"]
    assert all(d["id"] != did for d in listed)
