"""API: 客服在线状态（staff_presence.py）。

被测端点：
- POST /staff/api/v1/presence       自心跳（任何 staff）
- GET  /admin/api/v1/presence       后台总览（仅 supervisor/admin）

异常矩阵：
1. 心跳未登录 → 401
2. 心跳 happy → 200，DB upsert 一行
3. status 非法 → 静默回退 "online"（端点端的弱校验，详见 source）
4. /admin/presence 普通 agent → 403
5. /admin/presence supervisor / admin → 200，返回 all + active
6. /admin/presence manager → 403（require_roles 仅含 supervisor/admin）
7. offline 心跳 → 释放 human_pending 派单 + 返回 released_count
8. online 心跳 → 不释放派单 + 返回 released_count=0
9. away status → 收敛为 online（_VALID_STATUS 已不含 away）
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_presence import router as staff_presence_router
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.schema import now_str


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_presence_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestHeartbeatAuth:
    async def test_heartbeat_unauthenticated(self, init_self_db, client) -> None:
        resp = await client.post("/staff/api/v1/presence", json={"status": "online"})
        assert resp.status_code == 401


class TestHeartbeatHappyPath:
    async def test_heartbeat_writes_row(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.post(
            "/staff/api/v1/presence", json={"status": "online"}, headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["released_count"] == 0
        # DB 写一行
        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id=:s", {"s": "agent-1"}
        )
        assert row is not None
        assert row["status"] == "online"

    async def test_heartbeat_upsert_overwrites_status(
        self, init_self_db, client, agent_headers
    ) -> None:
        await client.post(
            "/staff/api/v1/presence", json={"status": "online"}, headers=agent_headers
        )
        await client.post(
            "/staff/api/v1/presence", json={"status": "offline"}, headers=agent_headers
        )
        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id=:s", {"s": "agent-1"}
        )
        assert row["status"] == "offline"

    async def test_heartbeat_invalid_status_falls_back_to_online(
        self, init_self_db, client, agent_headers
    ) -> None:
        """非白名单 status 静默改为 online（非 422，弱校验）。"""
        resp = await client.post(
            "/staff/api/v1/presence", json={"status": "nonsense"}, headers=agent_headers
        )
        assert resp.status_code == 200
        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id=:s", {"s": "agent-1"}
        )
        assert row["status"] == "online"

    @pytest.mark.parametrize("status", ["online", "offline"])
    async def test_heartbeat_valid_statuses(
        self, init_self_db, client, agent_headers, status: str
    ) -> None:
        resp = await client.post(
            "/staff/api/v1/presence", json={"status": status}, headers=agent_headers
        )
        assert resp.status_code == 200
        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id=:s", {"s": "agent-1"}
        )
        assert row["status"] == status

    async def test_heartbeat_empty_body_defaults_online(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.post(
            "/staff/api/v1/presence", json={}, headers=agent_headers
        )
        assert resp.status_code == 200
        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id=:s", {"s": "agent-1"}
        )
        assert row["status"] == "online"


class TestAdminPresenceListAuth:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        resp = await client.get("/admin/api/v1/presence")
        assert resp.status_code == 401

    async def test_agent_forbidden_403(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get("/admin/api/v1/presence", headers=agent_headers)
        assert resp.status_code == 403

    async def test_manager_forbidden_403(
        self, init_self_db, client, auth_headers
    ) -> None:
        """require_roles 仅含 supervisor/admin；manager 也被拒。"""
        resp = await client.get(
            "/admin/api/v1/presence", headers=auth_headers("manager")
        )
        assert resp.status_code == 403


class TestAdminPresenceListHappyPath:
    async def test_supervisor_can_list(
        self, init_self_db, client, supervisor_headers, agent_headers
    ) -> None:
        # agent-1 心跳
        await client.post(
            "/staff/api/v1/presence", json={"status": "online"}, headers=agent_headers
        )
        resp = await client.get(
            "/admin/api/v1/presence", headers=supervisor_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "all" in body
        assert "active" in body
        all_ids = {r["staff_id"] for r in body["all"]}
        assert "agent-1" in all_ids
        active_ids = {r["staff_id"] for r in body["active"]}
        assert "agent-1" in active_ids

    async def test_admin_can_list(
        self, init_self_db, client, admin_headers
    ) -> None:
        resp = await client.get("/admin/api/v1/presence", headers=admin_headers)
        assert resp.status_code == 200

    async def test_offline_staff_in_all_not_active(
        self, init_self_db, client, supervisor_headers, agent_headers
    ) -> None:
        # 先发心跳，再切 offline
        await client.post(
            "/staff/api/v1/presence", json={"status": "online"}, headers=agent_headers
        )
        await client.post(
            "/staff/api/v1/presence", json={"status": "offline"}, headers=agent_headers
        )
        resp = await client.get(
            "/admin/api/v1/presence", headers=supervisor_headers
        )
        body = resp.json()
        all_ids = {r["staff_id"] for r in body["all"]}
        active_ids = {r["staff_id"] for r in body["active"]}
        assert "agent-1" in all_ids
        assert "agent-1" not in active_ids


class TestOfflineSideEffects:
    """offline 心跳副作用：释放 human_pending 派单，返回 released_count。"""

    async def test_offline_releases_pending_returns_count(
        self, init_self_db, client, auth_headers
    ) -> None:
        sid = "agent-1"
        cid = await db_mod.insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, mode, assigned_staff_id, assigned_at, archived, created_at) "
            "VALUES ('c', 'u1', 'human_pending', :s, :t, 0, :now) RETURNING id",
            {"s": sid, "t": now_str(), "now": now_str()},
        )

        r = await client.post(
            "/staff/api/v1/presence",
            json={"status": "offline"},
            headers=auth_headers("agent", sub=sid),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["released_count"] == 1

        row = await db_mod.fetch_one(
            "SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": cid}
        )
        assert row["assigned_staff_id"] is None

    async def test_online_does_not_release(
        self, init_self_db, client, auth_headers
    ) -> None:
        sid = "agent-2"
        cid = await db_mod.insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, mode, assigned_staff_id, assigned_at, archived, created_at) "
            "VALUES ('c', 'u1', 'human_pending', :s, :t, 0, :now) RETURNING id",
            {"s": sid, "t": now_str(), "now": now_str()},
        )

        r = await client.post(
            "/staff/api/v1/presence",
            json={"status": "online"},
            headers=auth_headers("agent", sub=sid),
        )
        assert r.status_code == 200
        assert r.json()["released_count"] == 0

        row = await db_mod.fetch_one(
            "SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": cid}
        )
        assert row["assigned_staff_id"] == sid

    async def test_away_collapsed_to_online(
        self, init_self_db, client, auth_headers
    ) -> None:
        """away 不在 _VALID_STATUS 中，应静默回退为 online。"""
        r = await client.post(
            "/staff/api/v1/presence",
            json={"status": "away"},
            headers=auth_headers("agent", sub="agent-3"),
        )
        assert r.status_code == 200
        assert r.json()["released_count"] == 0

        row = await db_mod.fetch_one(
            "SELECT status FROM staff_presence WHERE staff_id='agent-3'"
        )
        assert row["status"] == "online"
