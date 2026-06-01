import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import rbac
    from ai_engine.persistence.staff import create_staff

    rbac.invalidate_cache()
    await create_staff("AD1", "管理员", "admin", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {
        "admin": issue_staff_token("AD1", "admin"),
        "agent": issue_staff_token("AG1", "agent"),
    }
    rbac.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_non_admin_forbidden(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/rbac/matrix", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_admin_get_matrix(env):
    async with await _c() as c:
        r = await c.get("/admin/api/v1/rbac/matrix", headers=_h(env["admin"]))
    assert r.status_code == 200
    matrix = r.json()["matrix"]
    assert "admin" in matrix and "agent" in matrix
    assert matrix["admin"]["admin.dashboard"] is True
    assert matrix["agent"]["admin.dashboard"] is False


async def test_admin_upsert_then_visible(env):
    async with await _c() as c:
        r = await c.put(
            "/admin/api/v1/rbac/matrix",
            json={"items": [
                {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
            ]},
            headers=_h(env["admin"]),
        )
        assert r.status_code == 200
        matrix = (await c.get("/admin/api/v1/rbac/matrix",
                              headers=_h(env["admin"]))).json()["matrix"]
    assert matrix["agent"]["admin.dashboard"] is True
