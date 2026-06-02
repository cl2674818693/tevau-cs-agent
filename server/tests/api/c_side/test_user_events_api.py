"""C 端 user-events / request-human / client-info 三组端点。

被测：
- POST /api/v1/conversations/{cid}/request-human
- POST /api/v1/tickets/{external_id}/user-events
- POST /api/v1/conversations/{cid}/client-info  # 客户端环境上报（upsert）

依赖 mock：
- create_ticket.run：避免真打事项中心 / Lark
- push_event_center：吞掉
"""

import json
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import client_info as ci_dao
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import tickets as ticket_dao

from .conftest import TOKEN_B, USER_CODE_A, auth_headers


# ────────── helper：屏蔽外部依赖 ──────────


@pytest.fixture
def _no_external(monkeypatch) -> None:
    """create_ticket.run + push_event_center 替成 stub。"""

    async def _fake_create_ticket(**kw: Any) -> dict[str, Any]:
        return {"external_ticket_id": "AI-FAKE-001"}

    monkeypatch.setattr(
        "ai_engine.api.user_events.create_ticket_run", _fake_create_ticket
    )

    async def _fake_push(_payload: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr("ai_engine.api.user_events.push_event_center", _fake_push)


# ────────── request-human ──────────


class TestRequestHuman:
    async def test_success_switches_to_pending(
        self, c_client: AsyncClient, conv_id: int, _no_external
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "rb"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["ticket_id"] == "AI-FAKE-001"
        mode, _ = await conv_dao.get_mode(conv_id)
        assert mode == "human_pending"

    async def test_idempotent_for_already_taken(
        self, c_client: AsyncClient, conv_id: int, _no_external
    ) -> None:
        await conv_dao.set_mode(conv_id, "human_takeover", assigned_staff_id="S001")
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={}
        )
        assert r.status_code == 200
        assert r.json()["note"] == "already human-handled"
        # 不应改回 pending
        mode, _ = await conv_dao.get_mode(conv_id)
        assert mode == "human_takeover"

    async def test_guest_forbidden_403(
        self, client: AsyncClient, conv_id: int, _no_external
    ) -> None:
        # 未登录 → guest，端点显式拒绝引导登录
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={}
        )
        assert r.status_code == 403

    async def test_other_user_forbidden_403(
        self, client: AsyncClient, conv_id: int, _no_external
    ) -> None:
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/request-human",
            json={},
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_nonexistent_conversation_returns_403(
        self, c_client: AsyncClient, _no_external
    ) -> None:
        r = await c_client.post(
            "/api/v1/conversations/9999999/request-human", json={}
        )
        assert r.status_code == 403

    async def test_optional_reason(
        self, c_client: AsyncClient, conv_id: int, _no_external
    ) -> None:
        # body 全空允许（reason 是 Optional）
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={}
        )
        assert r.status_code == 200


# ────────── user-events（对工单的回执） ──────────


@pytest_asyncio.fixture
async def my_ticket(conv_id: int) -> str:
    """直接写库，构造一条归属当前 USER_CODE_A 的 C 端工单。"""
    ext = "AI-TEST-USR-1"
    payload = {
        "source": "ai_engine",
        "external_ticket_id": ext,
        "user_type": "c",
        "user_id": USER_CODE_A,
        "category": "事务",
        "summary": "测试工单",
        "severity": "p2",
        "evidence": {},
        "created_at": "2026-06-01T00:00:00",
    }
    await ticket_dao.create_ticket(ext, conv_id, payload)
    return ext


class TestUserEvents:
    async def test_confirmed_resolved(
        self, c_client: AsyncClient, my_ticket: str, _no_external
    ) -> None:
        r = await c_client.post(
            f"/api/v1/tickets/{my_ticket}/user-events",
            json={"event": "user_confirmed_resolved"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # 应追加一条 closed 事件
        t = await ticket_dao.get_ticket(my_ticket)
        assert t and any(e["event"] == "closed" for e in t["events"])

    async def test_rejected_resolved(
        self, c_client: AsyncClient, my_ticket: str, _no_external
    ) -> None:
        r = await c_client.post(
            f"/api/v1/tickets/{my_ticket}/user-events",
            json={"event": "user_rejected_resolved", "reason": "卡还是用不了"},
        )
        assert r.status_code == 200
        t = await ticket_dao.get_ticket(my_ticket)
        ev = next(e for e in t["events"] if e["event"] == "reopen")
        assert "卡还是用不了" in str(ev["comment"])

    async def test_unknown_event_returns_400(
        self, c_client: AsyncClient, my_ticket: str, _no_external
    ) -> None:
        r = await c_client.post(
            f"/api/v1/tickets/{my_ticket}/user-events", json={"event": "wat"}
        )
        assert r.status_code == 400

    async def test_other_user_cannot_act_on_ticket(
        self, client: AsyncClient, my_ticket: str, _no_external
    ) -> None:
        r = await client.post(
            f"/api/v1/tickets/{my_ticket}/user-events",
            json={"event": "user_confirmed_resolved"},
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_nonexistent_ticket_returns_404(
        self, c_client: AsyncClient, _no_external
    ) -> None:
        r = await c_client.post(
            "/api/v1/tickets/AI-NO-SUCH/user-events",
            json={"event": "user_confirmed_resolved"},
        )
        assert r.status_code == 404

    async def test_missing_event_field_returns_422(
        self, c_client: AsyncClient, my_ticket: str, _no_external
    ) -> None:
        r = await c_client.post(
            f"/api/v1/tickets/{my_ticket}/user-events", json={}
        )
        assert r.status_code == 422


# ────────── client-info upsert ──────────


class TestClientInfo:
    async def test_inserts_first_report(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        body = {
            "platform": "iOS",
            "app_version": "1.2.3",
            "user_agent": "Mozilla/5.0",
        }
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/client-info", json=body
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        row = await ci_dao.get_client_info(conv_id)
        assert row["platform"] == "iOS"
        assert row["app_version"] == "1.2.3"

    async def test_upsert_overwrites(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/client-info",
            json={"platform": "Android", "app_version": "1.0.0"},
        )
        # 第二次上报：覆盖
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/client-info",
            json={"platform": "Android", "app_version": "2.0.0"},
        )
        row = await ci_dao.get_client_info(conv_id)
        assert row["app_version"] == "2.0.0"

    async def test_partial_payload_allowed(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        # 所有字段都是 Optional：空 body 应也接受
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/client-info", json={}
        )
        assert r.status_code == 200
        row = await ci_dao.get_client_info(conv_id)
        assert row["platform"] is None

    async def test_other_user_forbidden(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/client-info",
            json={"platform": "X"},
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_guest_cannot_report_to_c_conv(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        # guest 身份 user_type='g' 不匹配 conv.user_type='c' → 403
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/client-info", json={"platform": "X"}
        )
        assert r.status_code == 403

    async def test_nonexistent_conversation_returns_403(
        self, c_client: AsyncClient
    ) -> None:
        r = await c_client.post(
            "/api/v1/conversations/9999999/client-info", json={"platform": "X"}
        )
        assert r.status_code == 403
