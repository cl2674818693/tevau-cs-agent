import hashlib
import hmac
import json

from httpx import ASGITransport, AsyncClient


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def test_callback_records_event_in_db(seeded_db):
    from ai_engine import main as main_mod
    from ai_engine.config import settings
    from ai_engine.persistence.tickets import create_ticket, get_ticket

    ext_id = "AI-2026-05-18-cb"
    await create_ticket(external_id=ext_id, conversation_id=1, payload={"category": "bug"})

    body = {
        "event": "assigned",
        "actor": "嘉豪",
        "comment": "ok",
        "internal_ticket_id": "EC-1",
        "at": "now",
    }
    raw = json.dumps(body).encode("utf-8")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/tickets/{ext_id}/events",
            content=raw,
            headers={
                "X-Signature": _sign(raw, settings.event_center_secret),
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    t = await get_ticket(ext_id)
    assert any(e["event"] == "assigned" for e in t["events"])


async def test_callback_parses_severity_override(seeded_db):
    """spec §7.2 修订：event=in_progress 时可携带 severity（受理人覆盖）"""
    from ai_engine import main as main_mod
    from ai_engine.config import settings
    from ai_engine.persistence.tickets import create_ticket, get_ticket

    ext_id = "AI-2026-05-18-sev2"
    await create_ticket(
        external_id=ext_id, conversation_id=1, payload={"category": "bug", "severity": "p2"}
    )

    body = {
        "event": "in_progress",
        "actor": "嘉豪",
        "internal_ticket_id": "EC-2",
        "severity": "p0",
        "at": "now",
    }
    raw = json.dumps(body).encode("utf-8")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/tickets/{ext_id}/events",
            content=raw,
            headers={
                "X-Signature": _sign(raw, settings.event_center_secret),
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 200
    t = await get_ticket(ext_id)
    assert t["current_severity"] == "p0"


async def test_callback_rejects_bad_signature(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tickets/xxx/events",
            content=b'{"event":"x"}',
            headers={"X-Signature": "bad", "Content-Type": "application/json"},
        )
    assert resp.status_code == 401
