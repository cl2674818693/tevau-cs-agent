import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db
    from ai_engine.persistence.staff import create_staff

    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("AG1", "客服", "agent", "x")
    # 准备一通有客服接管历史的会话（user_type=b 走 X-BU-ID 鉴权方便测试）
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, assigned_staff_id, created_at) "
        "VALUES (1, 'b', 'BU1', 'human_takeover', 'AG1', '2026-05-30 00:00:00')"
    )
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (1, 'AG1', 'take', '2026-05-30 00:01:00')"
    )
    yield {"sup": issue_staff_token("SUP1", "supervisor")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def _c():
    from ai_engine import main as main_mod

    return AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t")


async def test_eligibility_for_taken_conversation(env):
    async with await _c() as c:
        r = await c.get(
            "/api/v1/conversations/1/agent-rating/eligibility",
            headers={"X-BU-ID": "BU1"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["eligible"] is True
    assert body["already_rated"] is False
    assert body["staff_id"] == "AG1"


async def test_eligibility_wrong_subject_403(env):
    async with await _c() as c:
        r = await c.get(
            "/api/v1/conversations/1/agent-rating/eligibility",
            headers={"X-BU-ID": "BU_OTHER"},
        )
    assert r.status_code == 403


async def test_submit_rating_and_become_already_rated(env):
    async with await _c() as c:
        r = await c.post(
            "/api/v1/conversations/1/agent-rating",
            json={"rating": 5, "comment": "赞"},
            headers={"X-BU-ID": "BU1"},
        )
        assert r.status_code == 200
        elig = (
            await c.get(
                "/api/v1/conversations/1/agent-rating/eligibility",
                headers={"X-BU-ID": "BU1"},
            )
        ).json()
    assert elig["already_rated"] is True


async def test_admin_aggregate(env):
    async with await _c() as c:
        await c.post(
            "/api/v1/conversations/1/agent-rating",
            json={"rating": 4, "comment": "OK"},
            headers={"X-BU-ID": "BU1"},
        )
        r = await c.get("/admin/api/v1/agent-ratings?staff_id=AG1", headers=_h(env["sup"]))
    assert r.status_code == 200
    body = r.json()
    assert body["aggregate"]["count"] == 1
    assert body["aggregate"]["avg_rating"] == 4.0
    assert any(it["rating"] == 4 for it in body["items"])


async def test_admin_agent_forbidden(env):
    from ai_engine.auth.staff_session import issue_staff_token

    agent_token = issue_staff_token("AG_X", "agent")
    async with await _c() as c:
        r = await c.get("/admin/api/v1/agent-ratings", headers=_h(agent_token))
    assert r.status_code == 403
