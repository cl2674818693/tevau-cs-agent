"""SLA 策略 /admin/api/v1/sla/policies 与 /admin/api/v1/sla/breaches。

被测：admin_sla CRUD + compute_breaches。
覆盖：鉴权矩阵；create 校验 metric 白名单 (400)；启用/禁用 (active=0)；
     delete 幂等；breaches 计算：take_time / resolve_time 双阈值；多策略取 min 阈值；
     无策略时 breaches 空；archived 会话不算。
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import db as db_mod


def _ago(seconds: int) -> str:
    """生成"N 秒前"的 UTC 字符串（compute_breaches 用 datetime.now(UTC) 减 created_at）。"""
    return (datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


@pytest.mark.usefixtures("init_self_db")
class TestSlaAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/admin/api/v1/sla/policies"),
            ("POST", "/admin/api/v1/sla/policies"),
            ("PATCH", "/admin/api/v1/sla/policies/1"),
            ("DELETE", "/admin/api/v1/sla/policies/1"),
            ("GET", "/admin/api/v1/sla/breaches"),
        ],
    )
    async def test_no_token_returns_401(self, client, method: str, path: str) -> None:
        kw = {}
        if method == "POST":
            kw = {"json": {"metric": "take_time", "threshold_seconds": 60}}
        elif method == "PATCH":
            kw = {"json": {"active": 0}}
        r = await client.request(method, path, **kw)
        assert r.status_code == 401

    @pytest.mark.parametrize("role", ["agent", "senior", "engineer", "manager"])
    async def test_non_sup_admin_forbidden(
        self, client, auth_headers, role: str
    ) -> None:
        r = await client.get("/admin/api/v1/sla/policies", headers=auth_headers(role))
        assert r.status_code == 403

    async def test_supervisor_pass(self, client, supervisor_headers) -> None:
        r = await client.get(
            "/admin/api/v1/sla/policies", headers=supervisor_headers
        )
        assert r.status_code == 200


@pytest.mark.usefixtures("init_self_db")
class TestSlaPolicyCrud:
    async def test_list_empty(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/sla/policies", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"policies": []}

    async def test_create_take_time(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["id"], int)

    async def test_create_resolve_time_with_scope(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={
                "metric": "resolve_time",
                "threshold_seconds": 1800,
                "scope": "user_type",
                "scope_value": "c",
            },
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_create_invalid_metric_400(self, client, admin_headers) -> None:
        """metric 不在 {take_time, resolve_time} → DAO ValueError → 400。"""
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "bogus_metric", "threshold_seconds": 60},
            headers=admin_headers,
        )
        assert r.status_code == 400

    async def test_create_missing_field_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_create_wrong_type_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": "not-a-number"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_list_returns_created(self, client, admin_headers) -> None:
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "resolve_time", "threshold_seconds": 1800},
            headers=admin_headers,
        )
        r = await client.get("/admin/api/v1/sla/policies", headers=admin_headers)
        rows = r.json()["policies"]
        assert len(rows) == 2
        metrics = {p["metric"] for p in rows}
        assert metrics == {"take_time", "resolve_time"}
        # 默认 active=1（schema server_default）
        assert all(int(p["active"]) == 1 for p in rows)

    async def test_patch_disable_then_breaches_skip(self, client, admin_headers) -> None:
        """patch active=0 → 该策略不再参与 compute_breaches。"""
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 1},
            headers=admin_headers,
        )
        pid = r.json()["id"]
        # 先造一个会触发 take_time 违规的会话
        await _make_pending_conv(seconds_ago=600)
        b1 = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert len(b1.json()["breaches"]) == 1
        # 禁用后 breaches 清空
        await client.patch(
            f"/admin/api/v1/sla/policies/{pid}",
            json={"active": 0},
            headers=admin_headers,
        )
        b2 = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert b2.json()["breaches"] == []

    async def test_patch_active_missing_returns_422(
        self, client, admin_headers
    ) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        pid = r.json()["id"]
        r2 = await client.patch(
            f"/admin/api/v1/sla/policies/{pid}",
            json={},
            headers=admin_headers,
        )
        assert r2.status_code == 422

    async def test_delete(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        pid = r.json()["id"]
        r2 = await client.delete(
            f"/admin/api/v1/sla/policies/{pid}", headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}
        r3 = await client.get("/admin/api/v1/sla/policies", headers=admin_headers)
        assert r3.json()["policies"] == []

    async def test_delete_nonexistent_returns_404(self, client, admin_headers) -> None:
        """DELETE 不存在 ID：DAO 返 rowcount=0 → 端点 404（bug #6 已修）。"""
        r = await client.delete(
            "/admin/api/v1/sla/policies/999999", headers=admin_headers,
        )
        assert r.status_code == 404


async def _make_pending_conv(seconds_ago: int) -> int:
    """造一个 human_pending 且 created_at = N 秒前的会话；返回 conv_id。"""
    return await db_mod.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, mode, archived, created_at) "
        "VALUES ('c', 'U-PEND', 'human_pending', 0, :now) RETURNING id",
        {"now": _ago(seconds_ago)},
    )


async def _take(conv_id: int, staff_id: str, seconds_ago: int) -> None:
    await db_mod.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:cid, :sid, 'take', :at)",
        {"cid": conv_id, "sid": staff_id, "at": _ago(seconds_ago)},
    )


@pytest.mark.usefixtures("init_self_db")
class TestSlaBreaches:
    async def test_no_policies_returns_empty(self, client, admin_headers) -> None:
        await _make_pending_conv(seconds_ago=99999)
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"breaches": []}

    async def test_take_time_breach_when_pending_too_long(
        self, client, admin_headers
    ) -> None:
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        cid = await _make_pending_conv(seconds_ago=600)
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        rows = r.json()["breaches"]
        assert len(rows) == 1
        assert rows[0]["conversation_id"] == cid
        assert rows[0]["metric"] == "take_time"
        assert rows[0]["threshold_seconds"] == 60
        assert rows[0]["elapsed_seconds"] >= 600

    async def test_take_time_not_breach_when_under_threshold(
        self, client, admin_headers
    ) -> None:
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 3600},
            headers=admin_headers,
        )
        await _make_pending_conv(seconds_ago=60)  # 1 分钟 < 1 小时
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert r.json()["breaches"] == []

    async def test_resolve_time_breach_when_taken_but_not_resolved(
        self, client, admin_headers
    ) -> None:
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "resolve_time", "threshold_seconds": 60},
            headers=admin_headers,
        )
        cid = await _make_pending_conv(seconds_ago=10000)
        await _take(cid, "s1", seconds_ago=600)
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        rows = r.json()["breaches"]
        # take_time 无策略，resolve_time 触发
        assert any(b["metric"] == "resolve_time" and b["conversation_id"] == cid for b in rows)

    async def test_resolved_conv_no_breach(self, client, admin_headers) -> None:
        """已 resolved 的会话不应在 breaches 中。"""
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "resolve_time", "threshold_seconds": 1},
            headers=admin_headers,
        )
        cid = await _make_pending_conv(seconds_ago=10000)
        await _take(cid, "s1", seconds_ago=600)
        await db_mod.execute(
            "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
            "VALUES (:cid, 's1', 'resolved', :at)",
            {"cid": cid, "at": _ago(0)},
        )
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert r.json()["breaches"] == []

    async def test_archived_conv_not_in_breaches(
        self, client, admin_headers
    ) -> None:
        """archived=1 的会话不算违规（compute_breaches WHERE archived=0）。"""
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 1},
            headers=admin_headers,
        )
        cid = await _make_pending_conv(seconds_ago=600)
        await db_mod.execute(
            "UPDATE conversations SET archived=1 WHERE id=:id", {"id": cid}
        )
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert r.json()["breaches"] == []

    async def test_multi_policies_use_min_threshold(
        self, client, admin_headers
    ) -> None:
        """同 metric 多策略时取最小阈值（compute_breaches 用 min）。"""
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 10},
            headers=admin_headers,
        )
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 99999},
            headers=admin_headers,
        )
        await _make_pending_conv(seconds_ago=300)
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        rows = r.json()["breaches"]
        assert len(rows) == 1
        # 命中的应该是较小阈值 10
        assert rows[0]["threshold_seconds"] == 10

    async def test_ai_mode_without_take_no_take_time_breach(
        self, client, admin_headers
    ) -> None:
        """take_time 仅对 mode=human_pending 计算；mode=ai 即使创建很久也不算。"""
        await client.post(
            "/admin/api/v1/sla/policies",
            json={"metric": "take_time", "threshold_seconds": 1},
            headers=admin_headers,
        )
        await db_mod.insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, mode, archived, created_at) "
            "VALUES ('c', 'U-AI', 'ai', 0, :now) RETURNING id",
            {"now": _ago(99999)},
        )
        r = await client.get("/admin/api/v1/sla/breaches", headers=admin_headers)
        assert r.json()["breaches"] == []

    async def test_anyio_no_op(self) -> None:
        """仅为占位：保证文件内不引入 unused import (asyncio)。"""
        await asyncio.sleep(0)
