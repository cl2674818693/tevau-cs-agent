import respx
from httpx import ASGITransport, AsyncClient, Response

_H = {"X-BU-ID": "BU00243780"}


async def _mk_ticket(ext_id: str, bu_id: str = "BU00243780"):
    from ai_engine.persistence.tickets import create_ticket

    await create_ticket(
        external_id=ext_id,
        conversation_id=1,
        payload={"category": "bug", "user_type": "b", "bu_id": bu_id},
    )


@respx.mock
async def test_user_confirmed_resolved_closes_and_pushes(temp_db_url, monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_URL", "http://ec")
    from ai_engine.config import settings

    settings.reload()
    respx.post("http://ec/events").mock(return_value=Response(200, json={"ok": True}))

    from ai_engine import main as main_mod
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import get_ticket

    await init_db()
    await _mk_ticket("AI-X")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-X/user-events",
            json={"event": "user_confirmed_resolved"},
            headers=_H,
        )
    assert r.status_code == 200
    t = await get_ticket("AI-X")
    assert any(e["event"] == "closed" for e in t["events"])


async def test_user_events_rejects_cross_identity(temp_db_url, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.persistence.db import init_db

    await init_db()
    await _mk_ticket("AI-Y", bu_id="BU_OTHER")  # 属于别的 BU

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-Y/user-events",
            json={"event": "user_confirmed_resolved"},
            headers=_H,
        )
    assert r.status_code == 403


async def test_user_events_unknown_event_400(temp_db_url, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.persistence.db import init_db

    await init_db()
    await _mk_ticket("AI-Z")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-Z/user-events", json={"event": "bogus"}, headers=_H
        )
    assert r.status_code == 400


async def test_request_human_sets_pending_and_creates_ticket(temp_db_url, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import create_ticket as ct
    from ai_engine.persistence.conversations import create_conversation, get_mode
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="b", subject_id="BU00243780")

    async def fake_post(url, json, headers):
        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(ct, "_post", fake_post)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/v1/conversations/{cid}/request-human",
            json={"reason": "AI 答非所问"},
            headers=_H,
        )
    assert r.status_code == 200
    assert r.json()["ticket_id"].startswith("AI-")
    mode, _ = await get_mode(cid)
    assert mode == "human_pending"
