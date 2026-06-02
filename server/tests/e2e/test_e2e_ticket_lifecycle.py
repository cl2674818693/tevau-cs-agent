"""E2E 剧本 #4：工单完整生命周期 created → pending → in_progress → resolved → closed。

剧本梗概：
    1. 用户求人工 → 工单建立（外部 ticket_id）。
    2. list_tickets(open=true) 可见，状态 pending（无事件）。
    3. 模拟事项中心回 webhook POST /api/v1/tickets/{ext_id}/events
       event=in_progress + severity=p1 → 本地镜像 severity 更新；status=in_progress；
       事件经会话总线 ticket-events-stream 投递。
    4. webhook resolved → status=resolved。
    5. 用户 user_confirmed_resolved → ticket_events 追加 closed → status=closed。
    6. 双 key 签名轮换：使用 previous key 签名仍能通过验签。

异常分支：
    - 错签名 → 401。
    - 已 closed 的工单仍能接收 event（事件链是 append-only）；但状态保持 closed。
    - 工单风暴对策：同 subject 24h 内再次 create_ticket 同 category 应附加证据而非新建。
"""

import hashlib
import hmac
import json
from typing import Any

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.config import settings
from ai_engine.persistence import tickets as ticket_dao


def _sign(body: bytes, key: str) -> str:
    return hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


@pytest_asyncio.fixture
async def ticket_id(c_client: AsyncClient) -> str:
    """建一条会话 + 调 request-human → 拿外部工单号。"""
    r = await c_client.post("/api/v1/conversations", json={})
    cid = int(r.json()["conversation_id"])
    r = await c_client.post(
        f"/api/v1/conversations/{cid}/request-human", json={"reason": "demo"}
    )
    return r.json()["ticket_id"]


@pytest_asyncio.fixture
def _hmac_keys(monkeypatch):
    """配置双 key 轮换；后续测试模拟外部 webhook 用任意一把签名都应通过。"""
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "current-secret-key")
    monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "previous-secret-key")
    settings.reload()
    yield "current-secret-key", "previous-secret-key"
    settings.reload()


class TestTicketLifecycle:
    async def test_created_ticket_appears_in_open_list(
        self, ticket_id: str, seeded_agent, make_staff_client
    ) -> None:
        sc = make_staff_client(seeded_agent, "agent")
        r = await sc.get("/staff/api/v1/tickets", params={"open": True})
        assert r.status_code == 200
        rows = r.json()["tickets"]
        ours = [t for t in rows if t["external_id"] == ticket_id]
        assert ours
        assert ours[0]["status"] == "pending"  # 无事件 → pending
        assert ours[0]["category"] == "人工介入"

    async def test_in_progress_event_updates_severity_and_status(
        self, client: AsyncClient, ticket_id: str, _hmac_keys, seeded_agent, make_staff_client
    ) -> None:
        cur_key, _ = _hmac_keys
        body = {
            "event": "in_progress",
            "actor": "ops",
            "comment": "已认领",
            "severity": "p1",
        }
        raw = json.dumps(body, ensure_ascii=False).encode()
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/events",
            content=raw,
            headers={"X-Signature": _sign(raw, cur_key), "Content-Type": "application/json"},
        )
        assert r.status_code == 200

        # 镜像 severity 已改
        t = await ticket_dao.get_ticket(ticket_id)
        assert t["current_severity"] == "p1"

        # 状态推断为 in_progress
        sc = make_staff_client(seeded_agent, "agent")
        rows = (await sc.get("/staff/api/v1/tickets")).json()["tickets"]
        ours = [r for r in rows if r["external_id"] == ticket_id]
        assert ours[0]["status"] == "in_progress"

    async def test_event_pushed_to_conversation_bus(
        self, client: AsyncClient, ticket_id: str, _hmac_keys
    ) -> None:
        """ticket event 应推到该会话的订阅总线（ticket-events-stream 消费）。"""
        cur_key, _ = _hmac_keys
        t = await ticket_dao.get_ticket(ticket_id)
        conv_id = int(t["conversation_id"])
        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        q = register_subscriber(conv_id)
        try:
            body = {"event": "in_progress", "actor": "ops", "severity": "p2"}
            raw = json.dumps(body, ensure_ascii=False).encode()
            r = await client.post(
                f"/api/v1/tickets/{ticket_id}/events",
                content=raw,
                headers={
                    "X-Signature": _sign(raw, cur_key),
                    "Content-Type": "application/json",
                },
            )
            assert r.status_code == 200
            import asyncio as _aio

            ev = await _aio.wait_for(q.get(), timeout=1.0)
            assert ev["type"] == "in_progress"
            assert ev["external_id"] == ticket_id
        finally:
            unregister_subscriber(conv_id, q)

    async def test_resolved_then_user_confirms_closes(
        self,
        c_client: AsyncClient,
        client: AsyncClient,
        ticket_id: str,
        _hmac_keys,
        seeded_agent,
        make_staff_client,
        _mock_event_center: list[dict[str, Any]],
    ) -> None:
        cur_key, _ = _hmac_keys
        # 1. 受理人 resolved
        body = {"event": "resolved", "actor": "ops"}
        raw = json.dumps(body, ensure_ascii=False).encode()
        await client.post(
            f"/api/v1/tickets/{ticket_id}/events",
            content=raw,
            headers={"X-Signature": _sign(raw, cur_key), "Content-Type": "application/json"},
        )
        # 状态推断 resolved
        sc = make_staff_client(seeded_agent, "agent")
        rows = (await sc.get("/staff/api/v1/tickets")).json()["tickets"]
        assert any(r["external_id"] == ticket_id and r["status"] == "resolved" for r in rows)

        # 2. 用户确认 closed
        _mock_event_center.clear()
        r = await c_client.post(
            f"/api/v1/tickets/{ticket_id}/user-events",
            json={"event": "user_confirmed_resolved"},
        )
        assert r.status_code == 200
        rows = (await sc.get("/staff/api/v1/tickets")).json()["tickets"]
        assert any(r["external_id"] == ticket_id and r["status"] == "closed" for r in rows)
        # 出口 push 也带 closed
        pushes = [it["push"] for it in _mock_event_center if "push" in it]
        assert any(p.get("event") == "closed" for p in pushes)

    async def test_rejected_resolution_reopens(
        self,
        c_client: AsyncClient,
        client: AsyncClient,
        ticket_id: str,
        _hmac_keys,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """resolved 后用户 reject → status=in_progress（reopen 事件映射）。"""
        cur_key, _ = _hmac_keys
        body = {"event": "resolved", "actor": "ops"}
        raw = json.dumps(body, ensure_ascii=False).encode()
        await client.post(
            f"/api/v1/tickets/{ticket_id}/events",
            content=raw,
            headers={"X-Signature": _sign(raw, cur_key), "Content-Type": "application/json"},
        )
        r = await c_client.post(
            f"/api/v1/tickets/{ticket_id}/user-events",
            json={"event": "user_rejected_resolved", "reason": "还没解决"},
        )
        assert r.status_code == 200
        sc = make_staff_client(seeded_agent, "agent")
        rows = (await sc.get("/staff/api/v1/tickets")).json()["tickets"]
        assert any(
            r["external_id"] == ticket_id and r["status"] == "in_progress" for r in rows
        )

    async def test_previous_key_signature_also_accepted(
        self, client: AsyncClient, ticket_id: str, _hmac_keys
    ) -> None:
        """spec §7.4 双 key 热轮换：用 previous key 签名同样应被接受。"""
        _, prev_key = _hmac_keys
        body = {"event": "in_progress", "actor": "ops"}
        raw = json.dumps(body, ensure_ascii=False).encode()
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/events",
            content=raw,
            headers={"X-Signature": _sign(raw, prev_key), "Content-Type": "application/json"},
        )
        assert r.status_code == 200

    async def test_bad_signature_returns_401(
        self, client: AsyncClient, ticket_id: str, _hmac_keys
    ) -> None:
        body = {"event": "in_progress"}
        raw = json.dumps(body).encode()
        r = await client.post(
            f"/api/v1/tickets/{ticket_id}/events",
            content=raw,
            headers={"X-Signature": "deadbeef", "Content-Type": "application/json"},
        )
        assert r.status_code == 401

    async def test_ticket_storm_appends_evidence_to_open_ticket(
        self, c_client: AsyncClient
    ) -> None:
        """24h 内同 subject 再次 request-human → 不新建工单，evidence 追加到原单。"""
        r1 = await c_client.post("/api/v1/conversations", json={})
        cid = int(r1.json()["conversation_id"])
        r1 = await c_client.post(
            f"/api/v1/conversations/{cid}/request-human", json={"reason": "first"}
        )
        first_id = r1.json()["ticket_id"]

        # 二次：另一个会话 + 同 subject_id
        r2 = await c_client.post("/api/v1/conversations", json={})
        cid2 = int(r2.json()["conversation_id"])
        r2 = await c_client.post(
            f"/api/v1/conversations/{cid2}/request-human", json={"reason": "again"}
        )
        # 复用首单 external_id（spec §11 工单风暴对策）
        assert r2.json()["ticket_id"] == first_id

        # 事件链里追加了 evidence_added
        t = await ticket_dao.get_ticket(first_id)
        events = [e["event"] for e in t["events"]]
        assert "evidence_added" in events
