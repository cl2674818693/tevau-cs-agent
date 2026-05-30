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

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    await db.execute(
        "INSERT INTO agent_ratings(conversation_id, staff_id, subject_id, user_type, "
        "rating, created_at) VALUES "
        "(1, 'AG1', 'u1', 'c', 5, '2026-06-01 00:00:00'), "
        "(2, 'AG2', 'u2', 'c', 3, '2026-06-01 01:00:00')"
    )
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
        r = await c.get("/admin/api/v1/reports", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_create_run_export_csv(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/reports",
            json={
                "name": "按客服评分",
                "source": "agent_ratings",
                "dims": ["staff_id"],
                "filters": [],
                "metrics": [{"op": "count", "col": "*", "alias": "n"}],
            },
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        run = await c.post(f"/admin/api/v1/reports/{rid}/run", headers=_h(env["sup"]))
        assert run.status_code == 200
        rows = run.json()["rows"]
        by = {row["staff_id"]: row for row in rows}
        assert by["AG1"]["n"] == 1
        csv = await c.get(f"/admin/api/v1/reports/{rid}/export.csv", headers=_h(env["sup"]))
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    text = csv.text
    assert "staff_id" in text and "AG1" in text


async def test_create_rejects_bad_source(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/reports",
            json={
                "name": "x", "source": "evil", "dims": [], "filters": [],
                "metrics": [{"op": "count", "col": "*", "alias": "n"}],
            },
            headers=_h(env["sup"]),
        )
    assert r.status_code == 400
