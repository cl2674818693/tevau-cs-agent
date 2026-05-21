from httpx import ASGITransport, AsyncClient


def _hist_count(metric: object, **labels: str) -> float:
    """从 Histogram 的 _count sample 取计数（child 无 _count 属性，走 collect）。"""
    for fam in metric.collect():  # type: ignore[attr-defined]
        for s in fam.samples:
            if s.name.endswith("_count") and all(s.labels.get(k) == v for k, v in labels.items()):
                return float(s.value)
    return 0.0


async def test_metrics_endpoint_exposes_prometheus(temp_db_url):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    # Gauge 始终存在
    assert "ai_engine_active_conversations" in r.text


async def test_tool_dispatch_increments_counter(temp_db_url):
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.observability import metrics
    from ai_engine.persistence.db import init_db

    await init_db()
    before = metrics.tool_calls.labels(tool="nope_tool", ok="false")._value.get()
    out = await dispatch(
        tool_name="nope_tool",
        params={},
        user_type="b",
        subject_id="BU1",
        conversation_id=1,
    )
    assert out["ok"] is False
    after = metrics.tool_calls.labels(tool="nope_tool", ok="false")._value.get()
    assert after == before + 1


async def test_user_resolved_counter(temp_db_url, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.observability import metrics
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket

    await init_db()
    await create_ticket(external_id="AI-M", conversation_id=1, payload={"bu_id": "BU1"})
    monkeypatch.setattr(
        "ai_engine.api.user_events.push_event_center", lambda *_a, **_k: _async_true()
    )

    before = metrics.user_resolved_total.labels(event="user_confirmed_resolved")._value.get()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-M/user-events",
            json={"event": "user_confirmed_resolved"},
            headers={"X-BU-ID": "BU1"},
        )
    assert r.status_code == 200
    after = metrics.user_resolved_total.labels(event="user_confirmed_resolved")._value.get()
    assert after == before + 1


async def _async_true() -> bool:
    return True


async def test_human_pending_gauge_tracks_db(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.observability import metrics
    from ai_engine.persistence.conversations import create_conversation, set_mode
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff_metrics import refresh_human_pending

    await init_db()
    c1 = await create_conversation("b", "BU1")
    await create_conversation("b", "BU2")
    await set_mode(c1, "human_pending")
    await refresh_human_pending()
    assert metrics.human_pending._value.get() == 1


async def test_staff_takeover_duration_observed(temp_db_url):
    from ai_engine.observability import metrics
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff_metrics import log_staff_action

    await init_db()
    before = _hist_count(metrics.staff_takeover_seconds, staff_id="SX")
    await log_staff_action(1, "SX", "take")
    await log_staff_action(1, "SX", "release")
    # take→release 配对后 observe 了一次
    assert _hist_count(metrics.staff_takeover_seconds, staff_id="SX") == before + 1


async def test_ticket_resolution_observed(temp_db_url, monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "k")
    from ai_engine.config import settings

    settings.reload()
    import hashlib
    import hmac
    import json

    from httpx import ASGITransport, AsyncClient

    from ai_engine import main as main_mod
    from ai_engine.observability import metrics
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket

    await init_db()
    await create_ticket(external_id="AI-R", conversation_id=1, payload={"category": "bug"})
    before = _hist_count(metrics.ticket_resolution_seconds, category="bug")

    raw = json.dumps({"event": "closed", "actor": "user"}).encode()
    sig = hmac.new(b"k", raw, hashlib.sha256).hexdigest()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-R/events",
            content=raw,
            headers={"X-Signature": sig, "Content-Type": "application/json"},
        )
    assert r.status_code == 200
    assert _hist_count(metrics.ticket_resolution_seconds, category="bug") == before + 1
