from httpx import ASGITransport, AsyncClient


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
