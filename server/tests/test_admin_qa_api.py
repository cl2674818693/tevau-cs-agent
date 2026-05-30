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
        r = await c.get("/admin/api/v1/qa/scorecards", headers=_h(env["agent"]))
    assert r.status_code == 403


async def test_scorecard_create_and_list(env):
    async with await _c() as c:
        r = await c.post(
            "/admin/api/v1/qa/scorecards",
            json={"name": "默认", "items": [{"key": "polite", "label": "礼貌", "weight": 1}]},
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (
            await c.get("/admin/api/v1/qa/scorecards", headers=_h(env["sup"]))
        ).json()["scorecards"]
    assert any(s["name"] == "默认" for s in listed)


async def test_submit_review_writes_audit(env):
    from ai_engine.persistence import admin_audit

    async with await _c() as c:
        sid_resp = await c.post(
            "/admin/api/v1/qa/scorecards",
            json={"name": "c1", "items": [{"key": "polite"}]},
            headers=_h(env["sup"]),
        )
        sid = sid_resp.json()["id"]
        r = await c.post(
            "/admin/api/v1/qa/reviews",
            json={
                "conversation_id": 7,
                "scorecard_id": sid,
                "score": 88,
                "items_result": {"polite": 1},
                "tags": "excellent",
                "comment": "好",
            },
            headers=_h(env["sup"]),
        )
        assert r.status_code == 200
        listed = (
            await c.get(
                "/admin/api/v1/qa/reviews?conversation_id=7", headers=_h(env["sup"])
            )
        ).json()["reviews"]
    assert len(listed) == 1 and listed[0]["score"] == 88
    audits = await admin_audit.list_admin_actions(action="qa.review.submit", limit=10)
    assert any(a["actor"] == "SUP1" for a in audits)
