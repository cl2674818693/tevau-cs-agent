import hashlib
import hmac

import respx
from httpx import Response


@respx.mock
async def test_push_event_center_signs_and_succeeds(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("EVENT_CENTER_URL", "http://ec")
    monkeypatch.setenv("EVENT_CENTER_SECRET", "shared")
    from ai_engine.config import settings

    settings.reload()

    route = respx.post("http://ec/events").mock(return_value=Response(200, json={"ok": True}))
    from ai_engine.integrations.event_center_client import push_event_center

    ok = await push_event_center({"external_ticket_id": "AI-1", "event_type": "closed"})
    assert ok is True
    sent = route.calls.last.request
    expected = hmac.new(b"shared", sent.content, hashlib.sha256).hexdigest()
    assert sent.headers["X-Signature"] == expected


@respx.mock
async def test_push_event_center_handles_failure(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("EVENT_CENTER_URL", "http://ec")
    from ai_engine.config import settings

    settings.reload()
    respx.post("http://ec/events").mock(return_value=Response(500))
    from ai_engine.integrations.event_center_client import push_event_center

    assert await push_event_center({"x": 1}) is False
