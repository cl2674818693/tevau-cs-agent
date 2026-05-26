import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def staff_token(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff

    await init_db()
    await create_staff("S100", "张三", "agent", "x")
    return issue_staff_token("S100", "agent")


async def _seed_tickets():
    from ai_engine.persistence.tickets import append_ticket_event, create_ticket

    # 三条工单：t1 open(p1)、t2 closed(p2)、t3 open(p0)
    await create_ticket(
        external_id="AI-T1",
        conversation_id=11,
        payload={"category": "bug", "severity": "p1"},
    )
    await create_ticket(
        external_id="AI-T2",
        conversation_id=12,
        payload={"category": "payment", "severity": "p2"},
    )
    await create_ticket(
        external_id="AI-T3",
        conversation_id=13,
        payload={"category": "bug", "severity": "p0"},
    )
    await append_ticket_event(
        external_id="AI-T2", event="closed", actor="嘉豪", comment="done"
    )


async def test_list_tickets_open_only_excludes_closed(staff_token):
    from ai_engine.persistence.tickets import list_tickets

    await _seed_tickets()
    rows = await list_tickets(open_only=True, severity=None, category=None, limit=50)
    ids = {r["external_id"] for r in rows}
    assert "AI-T2" not in ids  # 已关闭被排除
    assert {"AI-T1", "AI-T3"} <= ids
    # 字段齐全
    t1 = next(r for r in rows if r["external_id"] == "AI-T1")
    assert t1["category"] == "bug"
    assert t1["severity"] == "p1"
    assert t1["conversation_id"] == 11
    assert t1["created_at"]
    assert t1["closed"] is False


async def test_list_tickets_includes_closed_when_not_open_only(staff_token):
    from ai_engine.persistence.tickets import list_tickets

    await _seed_tickets()
    rows = await list_tickets(open_only=False, severity=None, category=None, limit=50)
    by_id = {r["external_id"]: r for r in rows}
    assert by_id["AI-T2"]["closed"] is True
    assert by_id["AI-T1"]["closed"] is False


async def test_list_tickets_filter_by_severity(staff_token):
    from ai_engine.persistence.tickets import list_tickets

    await _seed_tickets()
    rows = await list_tickets(open_only=False, severity="p0", category=None, limit=50)
    assert {r["external_id"] for r in rows} == {"AI-T3"}


async def test_list_tickets_filter_by_category(staff_token):
    from ai_engine.persistence.tickets import list_tickets

    await _seed_tickets()
    rows = await list_tickets(open_only=False, severity=None, category="bug", limit=50)
    assert {r["external_id"] for r in rows} == {"AI-T1", "AI-T3"}


async def test_tickets_endpoint_requires_auth(staff_token):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/staff/api/v1/tickets")  # 无 token
    assert r.status_code == 401


async def test_tickets_endpoint_returns_list(staff_token):
    from ai_engine import main as main_mod

    await _seed_tickets()
    transport = ASGITransport(app=main_mod.app)
    headers = {"Authorization": f"Bearer {staff_token}"}
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/staff/api/v1/tickets?open=true", headers=headers)
    assert r.status_code == 200
    body = r.json()
    ids = {t["external_id"] for t in body["tickets"]}
    assert "AI-T2" not in ids
    assert {"AI-T1", "AI-T3"} <= ids
