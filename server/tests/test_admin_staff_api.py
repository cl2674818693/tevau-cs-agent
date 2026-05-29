import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AD1", "管理员", "admin", "x")
    await create_staff("AG1", "客服", "agent", "x")
    yield {"admin": issue_staff_token("AD1", "admin"), "agent": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _client():
    from ai_engine import main as main_mod
    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_list_requires_admin(env):
    async with await _client() as c:
        assert (await c.get("/admin/api/v1/staff", headers=_h(env["agent"]))).status_code == 403
        r = await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))
    assert r.status_code == 200
    assert any(s["staff_id"] == "AD1" for s in r.json()["staff"])


async def test_create_staff(env):
    async with await _client() as c:
        payload = {
            "staff_id": "SUP1", "display_name": "主管", "role": "supervisor", "password": "pw"
        }
        r = await c.post(
            "/admin/api/v1/staff",
            json=payload,
            headers=_h(env["admin"]),
        )
    assert r.status_code == 200
    async with await _client() as c:
        listed = (await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))).json()["staff"]
    assert any(s["staff_id"] == "SUP1" and s["role"] == "supervisor" for s in listed)


async def test_create_rejects_bad_role(env):
    async with await _client() as c:
        r = await c.post(
            "/admin/api/v1/staff",
            json={"staff_id": "X", "display_name": "x", "role": "ceo", "password": "pw"},
            headers=_h(env["admin"]),
        )
    assert r.status_code == 400


async def test_patch_and_reset(env):
    async with await _client() as c:
        await c.patch("/admin/api/v1/staff/AG1", json={"role": "senior"}, headers=_h(env["admin"]))
        await c.post(
            "/admin/api/v1/staff/AG1/reset-password",
            json={"password": "np"},
            headers=_h(env["admin"]),
        )
        listed = (await c.get("/admin/api/v1/staff", headers=_h(env["admin"]))).json()["staff"]
    assert next(s for s in listed if s["staff_id"] == "AG1")["role"] == "senior"


async def test_create_writes_audit(env):
    from ai_engine.persistence import admin_audit
    async with await _client() as c:
        await c.post(
            "/admin/api/v1/staff",
            json={"staff_id": "AG9", "display_name": "x", "role": "agent", "password": "pw"},
            headers=_h(env["admin"]),
        )
    rows = await admin_audit.list_admin_actions(action="staff.create", limit=10)
    assert any(r["target_id"] == "AG9" and r["actor"] == "AD1" for r in rows)
