"""API: POST /api/v1/tickets/{external_id}/events（tickets.receive_event）。

被测对象：事项中心回调入口 → HMAC 双 key 验签（spec §7.4 current/previous 任一过即可）。
HMAC = HMAC-SHA256(secret, raw_body).hexdigest()，header 名 X-Signature。

异常矩阵（题面）：
10. HMAC 签名错 → 401
11. HMAC 双 key 轮换：current 与 previous 任一签都能过 → 200
+ 配套：
- 双 key 都空 → 任何签名都 401
- 触发 in_progress 带 severity 时更新 current_severity
- 事件不在指派的 conversation_id 时不崩（仅静默不广播）
- 触发 resolved 时计入 prometheus histogram
"""

import hashlib
import hmac
import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.tickets import router as tickets_router
from ai_engine.config import settings
from ai_engine.persistence import db as db_mod

from .conftest import insert_conversation, insert_ticket


def _sig(secret: str, raw: bytes) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(tickets_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def with_current_secret(monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "secret-current-AAA")
    monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "")
    settings.reload()
    yield "secret-current-AAA"
    settings.reload()


@pytest.fixture
def with_both_secrets(monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "current-key-XXX")
    monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "previous-key-YYY")
    settings.reload()
    yield ("current-key-XXX", "previous-key-YYY")
    settings.reload()


class TestSignatureValidation:
    async def test_correct_signature_passes(
        self, init_self_db, client, with_current_secret
    ) -> None:
        secret = with_current_secret
        # 先建一条工单（receive_event 会查 get_ticket 推 SSE）
        cid = await insert_conversation()
        await insert_ticket("T-001", cid)
        body = {"event": "in_progress", "actor": "eng-1", "comment": "working"}
        raw = json.dumps(body).encode()
        resp = await client.post(
            "/api/v1/tickets/T-001/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(secret, raw),
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_wrong_signature_401(
        self, init_self_db, client, with_current_secret
    ) -> None:
        raw = b'{"event":"in_progress"}'
        resp = await client.post(
            "/api/v1/tickets/T-001/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": "deadbeef" * 8,
            },
        )
        assert resp.status_code == 401
        assert "bad signature" in resp.json()["detail"]

    async def test_missing_signature_401(
        self, init_self_db, client, with_current_secret
    ) -> None:
        resp = await client.post(
            "/api/v1/tickets/T-001/events", json={"event": "in_progress"}
        )
        assert resp.status_code == 401

    async def test_both_keys_empty_rejects_any(
        self, init_self_db, client, monkeypatch
    ) -> None:
        """current+previous 都空 → 任何签名都 401（默认空配置防 dev 误调）。"""
        monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "")
        monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "")
        settings.reload()
        raw = b'{"event":"in_progress"}'
        # 用空 key 算签名（攻击者可猜出）也应被拒
        sig = _sig("", raw)
        resp = await client.post(
            "/api/v1/tickets/T-001/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": sig,
            },
        )
        assert resp.status_code == 401


class TestDualKeyRotation:
    """spec §7.4：current/previous 任一通过即可，支持热轮换。"""

    async def test_current_key_passes(
        self, init_self_db, client, with_both_secrets
    ) -> None:
        current, _previous = with_both_secrets
        cid = await insert_conversation()
        await insert_ticket("T-cur", cid)
        raw = json.dumps({"event": "in_progress"}).encode()
        resp = await client.post(
            "/api/v1/tickets/T-cur/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(current, raw),
            },
        )
        assert resp.status_code == 200

    async def test_previous_key_also_passes(
        self, init_self_db, client, with_both_secrets
    ) -> None:
        """previous key 在轮换窗口内也能通过（防旧客户端立刻断）。"""
        _current, previous = with_both_secrets
        cid = await insert_conversation()
        await insert_ticket("T-prev", cid)
        raw = json.dumps({"event": "resolved"}).encode()
        resp = await client.post(
            "/api/v1/tickets/T-prev/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(previous, raw),
            },
        )
        assert resp.status_code == 200

    async def test_neither_key_rejects(
        self, init_self_db, client, with_both_secrets
    ) -> None:
        raw = b'{"event":"x"}'
        resp = await client.post(
            "/api/v1/tickets/T-neither/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig("not-a-key", raw),
            },
        )
        assert resp.status_code == 401


class TestEventPersistence:
    async def test_event_writes_row(
        self, init_self_db, client, with_current_secret
    ) -> None:
        secret = with_current_secret
        cid = await insert_conversation()
        await insert_ticket("T-001", cid)
        raw = json.dumps({"event": "in_progress", "actor": "x", "comment": "y"}).encode()
        await client.post(
            "/api/v1/tickets/T-001/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(secret, raw),
            },
        )
        rows = await db_mod.fetch_all(
            "SELECT event, actor, comment FROM ticket_events WHERE external_id=:e",
            {"e": "T-001"},
        )
        assert len(rows) == 1
        assert rows[0]["event"] == "in_progress"
        assert rows[0]["actor"] == "x"
        assert rows[0]["comment"] == "y"

    async def test_in_progress_updates_severity_when_provided(
        self, init_self_db, client, with_current_secret
    ) -> None:
        secret = with_current_secret
        cid = await insert_conversation()
        await insert_ticket("T-sev", cid, severity="P3")
        raw = json.dumps({"event": "in_progress", "severity": "P1"}).encode()
        resp = await client.post(
            "/api/v1/tickets/T-sev/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(secret, raw),
            },
        )
        assert resp.status_code == 200
        row = await db_mod.fetch_one(
            "SELECT current_severity FROM tickets WHERE external_id=:e", {"e": "T-sev"}
        )
        assert row["current_severity"] == "P1"

    async def test_event_for_unknown_ticket_still_writes_event_row(
        self, init_self_db, client, with_current_secret
    ) -> None:
        """工单本地未镜像也写事件行（外部事项中心是真源，本地仅审计）。"""
        secret = with_current_secret
        raw = json.dumps({"event": "in_progress"}).encode()
        resp = await client.post(
            "/api/v1/tickets/T-unknown/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(secret, raw),
            },
        )
        assert resp.status_code == 200
        rows = await db_mod.fetch_all(
            "SELECT event FROM ticket_events WHERE external_id=:e", {"e": "T-unknown"}
        )
        assert len(rows) == 1

    async def test_resolved_event_handled(
        self, init_self_db, client, with_current_secret
    ) -> None:
        """resolved/closed 进入 _observe_resolution，不应崩。"""
        secret = with_current_secret
        cid = await insert_conversation()
        await insert_ticket("T-res", cid)
        raw = json.dumps({"event": "resolved"}).encode()
        resp = await client.post(
            "/api/v1/tickets/T-res/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Signature": _sig(secret, raw),
            },
        )
        assert resp.status_code == 200
