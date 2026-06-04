"""API: 工单只读 CRUD（tickets.py 中的 GET 端点）。

被测端点：
- GET /staff/api/v1/tickets       列表（filter: open / severity / category / before_id）
- GET /staff/api/v1/tickets/{external_id}   详情含事件链

注：建/更新都不暴露 staff endpoint —— 工单由外部事项中心通过 callback 写入（见 test_tickets_callback_api.py）。
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.tickets import router as tickets_router

from .conftest import insert_conversation, insert_ticket, insert_ticket_event


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(tickets_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestListAuth:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/tickets")
        assert resp.status_code == 401


class TestListHappyPath:
    async def test_empty_list(self, init_self_db, client, agent_headers) -> None:
        resp = await client.get("/staff/api/v1/tickets", headers=agent_headers)
        assert resp.status_code == 200
        assert resp.json() == {"tickets": []}

    async def test_list_returns_all_by_default(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-001", cid, severity="P1", category="card")
        await insert_ticket("T-002", cid, severity="P2", category="kyc")
        resp = await client.get("/staff/api/v1/tickets", headers=agent_headers)
        assert resp.status_code == 200
        tks = resp.json()["tickets"]
        ids = {t["external_id"] for t in tks}
        assert ids == {"T-001", "T-002"}
        # status 默认 pending（无事件）
        assert all(t["status"] == "pending" for t in tks)

    async def test_filter_open_only(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-A", cid)
        await insert_ticket("T-B", cid)
        await insert_ticket_event("T-A", "closed")
        resp = await client.get(
            "/staff/api/v1/tickets?open=true", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-B"}

    async def test_filter_severity(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-1", cid, severity="P1")
        await insert_ticket("T-2", cid, severity="P3")
        resp = await client.get(
            "/staff/api/v1/tickets?severity=P1", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-1"}

    async def test_filter_category(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-c1", cid, category="card")
        await insert_ticket("T-k1", cid, category="kyc")
        resp = await client.get(
            "/staff/api/v1/tickets?category=card", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-c1"}

    async def test_status_resolved_for_resolved_event(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-R", cid)
        await insert_ticket_event("T-R", "in_progress")
        await insert_ticket_event("T-R", "resolved")
        resp = await client.get("/staff/api/v1/tickets", headers=agent_headers)
        t = next(t for t in resp.json()["tickets"] if t["external_id"] == "T-R")
        assert t["status"] == "resolved"
        assert t["closed"] is False

    async def test_status_in_progress_for_user_rejected(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-U", cid)
        await insert_ticket_event("T-U", "resolved")
        await insert_ticket_event("T-U", "user_rejected_resolved")
        resp = await client.get("/staff/api/v1/tickets", headers=agent_headers)
        t = next(t for t in resp.json()["tickets"] if t["external_id"] == "T-U")
        assert t["status"] == "in_progress"

    async def test_status_closed_marked_closed_flag(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-Z", cid)
        await insert_ticket_event("T-Z", "closed")
        resp = await client.get("/staff/api/v1/tickets", headers=agent_headers)
        t = next(t for t in resp.json()["tickets"] if t["external_id"] == "T-Z")
        assert t["status"] == "closed"
        assert t["closed"] is True

    async def test_filter_status_pending(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-pending", cid)
        await insert_ticket("T-prog", cid)
        await insert_ticket_event("T-prog", "in_progress")
        resp = await client.get(
            "/staff/api/v1/tickets?status=pending", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-pending"}

    async def test_filter_status_in_progress(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-prog", cid)
        await insert_ticket("T-resolved", cid)
        await insert_ticket("T-closed", cid)
        await insert_ticket_event("T-prog", "in_progress")
        await insert_ticket_event("T-resolved", "resolved")
        await insert_ticket_event("T-closed", "closed")
        resp = await client.get(
            "/staff/api/v1/tickets?status=in_progress", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-prog"}

    async def test_filter_status_resolved(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-r1", cid)
        await insert_ticket("T-r2", cid)
        await insert_ticket_event("T-r1", "resolved")
        await insert_ticket_event("T-r2", "user_confirmed_resolved")
        resp = await client.get(
            "/staff/api/v1/tickets?status=resolved", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-r1", "T-r2"}

    async def test_filter_status_closed(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-c", cid)
        await insert_ticket("T-r", cid)
        await insert_ticket_event("T-c", "closed")
        await insert_ticket_event("T-r", "resolved")
        resp = await client.get(
            "/staff/api/v1/tickets?status=closed", headers=agent_headers
        )
        ids = {t["external_id"] for t in resp.json()["tickets"]}
        assert ids == {"T-c"}

    async def test_invalid_status_422(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get(
            "/staff/api/v1/tickets?status=bogus", headers=agent_headers
        )
        assert resp.status_code == 422

    async def test_limit_validation(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get(
            "/staff/api/v1/tickets?limit=500", headers=agent_headers
        )
        assert resp.status_code == 422


class TestGetTicketDetail:
    async def test_get_happy(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        await insert_ticket("T-D", cid, severity="P2")
        await insert_ticket_event("T-D", "assigned", actor="eng-1")
        await insert_ticket_event("T-D", "in_progress")
        resp = await client.get("/staff/api/v1/tickets/T-D", headers=agent_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["external_id"] == "T-D"
        assert body["current_severity"] == "P2"
        events = body["events"]
        assert len(events) == 2
        assert events[0]["event"] == "assigned"
        assert events[0]["actor"] == "eng-1"
        assert events[1]["event"] == "in_progress"

    async def test_get_not_found_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get(
            "/staff/api/v1/tickets/NOPE", headers=agent_headers
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_get_unauthenticated_401(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/tickets/T-001")
        assert resp.status_code == 401
