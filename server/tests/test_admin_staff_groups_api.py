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
    await create_staff("AD1", "管理员", "admin", "x")
    yield {
        "sup": issue_staff_token("SUP1", "supervisor"),
        "agent": issue_staff_token("AG1", "agent"),
        "admin": issue_staff_token("AD1", "admin"),
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
        r = await c.get("/admin/api/v1/staff-groups", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_group(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/staff-groups",
            json={"name": "证券组", "description": "证券"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (
            await c.get("/admin/api/v1/staff-groups", headers=_h(env["sup"]))
        ).json()["groups"]
    assert any(g["name"] == "证券组" for g in listed)


async def test_patch_staff_group_and_skills(env):
    async with await _c() as c:
        r0 = await c.post(
            "/admin/api/v1/staff-groups",
            json={"name": "g1", "description": None},
            headers=_h(env["sup"]),
        )
        gid = r0.json()["id"]
        r = await c.patch(
            "/admin/api/v1/staff/AG1",
            json={"group_id": gid, "skills": ["c", "stock"]},
            headers=_h(env["admin"]),
        )
        assert r.status_code == 200
        listed = (
            await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))
        ).json()["staff"]
    ag1 = next(s for s in listed if s["staff_id"] == "AG1")
    assert int(ag1["group_id"]) == gid
    import json
    assert json.loads(ag1["skills"]) == ["c", "stock"]
