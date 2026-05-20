import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
async def env(temp_db_url, monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "sse-key")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.db import init_db

    await init_db()


async def test_webhook_publishes_ticket_event_to_bus(env):
    from ai_engine import main as main_mod
    from ai_engine.api import staff_conversations as sc
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.tickets import create_ticket

    cid = await create_conversation("b", "BU1")
    await create_ticket(external_id="AI-9", conversation_id=cid, payload={"category": "bug"})
    q = sc.register_subscriber(cid)

    body = {"event": "assigned", "actor": "staff", "internal_ticket_id": "EC"}
    raw = json.dumps(body).encode()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-9/events",
            content=raw,
            headers={"X-Signature": _sign(raw, "sse-key"), "Content-Type": "application/json"},
        )
    assert r.status_code == 200

    ev = q.get_nowait()
    sc.unregister_subscriber(cid, q)
    assert ev["type"] == "assigned"
    assert ev["external_id"] == "AI-9"


async def test_ticket_stream_rejects_cross_subject(env):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU1")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            f"/api/v1/conversations/{cid}/ticket-events-stream",
            headers={"X-BU-ID": "BU_OTHER"},
        )
    assert r.status_code == 403


def test_ticket_event_types_filter():
    from ai_engine.api.ticket_events_sse import TICKET_EVENT_TYPES

    assert "assigned" in TICKET_EVENT_TYPES
    assert "resolved" in TICKET_EVENT_TYPES
    assert "human_message" not in TICKET_EVENT_TYPES  # 客服消息不进工单流
