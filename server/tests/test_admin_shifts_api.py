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
        r = await c.get("/admin/api/v1/shifts", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_list_delete_shift(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "AG1", "start_at": "2026-06-01 09:00:00",
                  "end_at": "2026-06-01 18:00:00"},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        sid = r.json()["id"]
        listed = (await c.get("/admin/api/v1/shifts?staff_id=AG1",
                              headers=_h(env["sup"]))).json()["shifts"]
        assert any(s["id"] == sid for s in listed)
        del_r = await c.delete(f"/admin/api/v1/shifts/{sid}", headers=_h(env["sup"]))
        assert del_r.status_code == 200
        listed_after = (await c.get("/admin/api/v1/shifts?staff_id=AG1",
                                    headers=_h(env["sup"]))).json()["shifts"]
        assert all(s["id"] != sid for s in listed_after)
