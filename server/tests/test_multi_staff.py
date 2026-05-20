import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("EN1", "工程师", "engineer", "x")
    await create_staff("AG2", "客服2", "agent", "x")
    return {
        "agent": issue_staff_token("AG1", "agent"),
        "eng": issue_staff_token("EN1", "engineer"),
    }


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_agent_can_transfer_to_engineer(env):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode

    cid = await create_conversation("b", "BU1")
    await set_mode(cid, "human_takeover", "AG1")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/EN1", headers=_h(env["agent"])
        )
        assert r.status_code == 200
    mode, sid = await get_mode(cid)
    assert mode == "human_takeover" and sid == "EN1"


async def test_agent_cannot_transfer_to_agent(env):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, set_mode

    cid = await create_conversation("b", "BU1")
    await set_mode(cid, "human_takeover", "AG1")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/AG2", headers=_h(env["agent"])
        )
    assert r.status_code == 403


async def test_transfer_unknown_target_404(env):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, set_mode

    cid = await create_conversation("b", "BU1")
    await set_mode(cid, "human_takeover", "EN1")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/NOPE", headers=_h(env["eng"])
        )
    assert r.status_code == 404


async def test_kpi_aggregates_actions(env):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # AG1 接管会话1 → 解决
        c1 = await create_conversation("b", "BU1")
        await client.post(f"/staff/api/v1/conversations/{c1}/take", headers=_h(env["agent"]))
        await client.post(f"/staff/api/v1/conversations/{c1}/resolve", headers=_h(env["agent"]))
        # AG1 接管会话2 → 释放回 AI（未解决）
        c2 = await create_conversation("b", "BU2")
        await client.post(f"/staff/api/v1/conversations/{c2}/take", headers=_h(env["agent"]))
        await client.post(f"/staff/api/v1/conversations/{c2}/release", headers=_h(env["agent"]))

        r = await client.get("/staff/api/v1/kpi", headers=_h(env["agent"]))
        assert r.status_code == 200
        rows = {row["staff_id"]: row for row in r.json()["staff"]}

    ag = rows["AG1"]
    assert ag["takeovers"] == 2
    assert ag["resolved"] == 1
    assert ag["releases"] == 1
    assert ag["resolved_ratio"] == 0.5
