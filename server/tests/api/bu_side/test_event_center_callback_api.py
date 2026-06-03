"""API: POST /api/v1/event-center/callback（event_center_callback.callback）。

事项中心契约改造后入站协议：
- Bearer token 验签（替代旧 HMAC X-Signature）
- body 含 task_id / event_id / status=completed / resolution / handled_by / resolve_seconds
- 收到后落 ticket_events 表 + 推 SSE + closed 入解决耗时 metric

覆盖：
- 401（缺 / 错 token）
- 503（未配 token）
- 200（合法 callback + 落 event + 解决耗时 metric）
- 404（event_id 不存在本地）
- status=completed → event_name="closed"；其他 status 透传
"""

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from ai_engine.api.event_center_callback import router as cb_router
from ai_engine.config import settings
from ai_engine.persistence import db as pg
from ai_engine.persistence.tickets import create_ticket as _save_ticket


VALID_TOKEN = "test-callback-token"
EXT_ID = "AI-2026-06-03-test01"


@pytest.fixture
def _configure_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "event_center_callback_token", VALID_TOKEN)


@pytest.fixture
def client(make_client, init_self_db):
    app = FastAPI()
    app.include_router(cb_router)
    return make_client(app)


@pytest.fixture
async def _seed_ticket(init_self_db) -> str:
    """造一条本地 ticket 让 callback 能查到。"""
    payload: dict[str, Any] = {
        "source": "ai_engine",
        "external_ticket_id": EXT_ID,
        "category": "bug",
        "severity": "p2",
        "user_id": "U001",
    }
    await _save_ticket(external_id=EXT_ID, conversation_id=1, payload=payload)
    return EXT_ID


def _body() -> dict[str, Any]:
    return {
        "task_id": 100,
        "event_id": EXT_ID,
        "source_ref": EXT_ID,
        "event_type": "new_ticket",
        "status": "completed",
        "resolution": "已联系用户协助完成",
        "resolution_type": "manual_correction",
        "handled_by": "客服A",
        "resolved_at": "2026-06-03T15:10:00Z",
        "resolve_seconds": 2400,
    }


class TestTokenValidation:
    async def test_missing_token_401(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        r = await client.post("/api/v1/event-center/callback", json=_body())
        assert r.status_code == 401

    async def test_wrong_token_401(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        r = await client.post(
            "/api/v1/event-center/callback",
            json=_body(),
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    async def test_wrong_scheme_401(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        # 错 scheme（Basic 而非 Bearer）应被拒
        r = await client.post(
            "/api/v1/event-center/callback",
            json=_body(),
            headers={"Authorization": f"Basic {VALID_TOKEN}"},
        )
        assert r.status_code == 401

    async def test_correct_token_200(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        r = await client.post(
            "/api/v1/event-center/callback",
            json=_body(),
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    async def test_token_not_configured_503(
        self, client: AsyncClient, monkeypatch, _seed_ticket
    ) -> None:
        # 防漏配：未配 callback_token 时所有入站一律拒绝（避免裸奔）
        monkeypatch.setattr(settings, "event_center_callback_token", "")
        r = await client.post(
            "/api/v1/event-center/callback",
            json=_body(),
            headers={"Authorization": "Bearer anything"},
        )
        assert r.status_code == 503


class TestEventPersistence:
    async def test_completed_writes_closed_event(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        r = await client.post(
            "/api/v1/event-center/callback",
            json=_body(),
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert r.status_code == 200
        # 落 ticket_events 表：status=completed → event=closed
        row = await pg.fetch_one(
            "SELECT event, actor, comment FROM ticket_events WHERE external_id=:eid",
            {"eid": EXT_ID},
        )
        assert row is not None
        assert row["event"] == "closed"
        assert row["actor"] == "客服A"
        assert row["comment"] == "已联系用户协助完成"

    async def test_unknown_event_id_404(
        self, client: AsyncClient, _configure_token
    ) -> None:
        body = _body()
        body["event_id"] = "AI-NOT-EXIST"
        r = await client.post(
            "/api/v1/event-center/callback",
            json=body,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert r.status_code == 404

    async def test_unknown_status_passthrough(
        self, client: AsyncClient, _configure_token, _seed_ticket
    ) -> None:
        # 未来事项中心扩 status=cancelled 等，event_name 透传原值（不强制翻译成 closed）
        body = _body()
        body["status"] = "cancelled"
        r = await client.post(
            "/api/v1/event-center/callback",
            json=body,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )
        assert r.status_code == 200
        row = await pg.fetch_one(
            "SELECT event FROM ticket_events WHERE external_id=:eid",
            {"eid": EXT_ID},
        )
        assert row is not None and row["event"] == "cancelled"
