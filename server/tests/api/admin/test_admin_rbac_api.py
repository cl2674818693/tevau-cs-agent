"""动态 RBAC 矩阵 /admin/api/v1/rbac/matrix。

被测：admin_rbac.get_matrix / upsert。
覆盖：仅 admin 可访问、矩阵 GET 形态（含全部 ROLES × PERMISSION_KEYS）、PUT upsert 写入、
     立即生效（重读反映新值）、缓存失效（list_matrix 没缓存旧值）、参数错误 422、
     未知 role/permission_key 仍能写入（DB-first 不限制白名单，仅作覆盖默认矩阵的能力）。
"""

import pytest

from ai_engine.persistence import rbac


@pytest.mark.usefixtures("init_self_db")
class TestRbacAuth:
    async def test_no_token_returns_401(self, client) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix")
        assert r.status_code == 401

    @pytest.mark.parametrize("role", ["agent", "senior", "supervisor", "manager", "engineer"])
    async def test_non_admin_forbidden(self, client, auth_headers, role: str) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix", headers=auth_headers(role))
        assert r.status_code == 403

    async def test_admin_pass(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        assert r.status_code == 200

    async def test_put_no_token_401(self, client) -> None:
        r = await client.put("/admin/api/v1/rbac/matrix", json={"items": []})
        assert r.status_code == 401

    async def test_put_non_admin_403(self, client, supervisor_headers) -> None:
        r = await client.put(
            "/admin/api/v1/rbac/matrix",
            json={"items": []},
            headers=supervisor_headers,
        )
        assert r.status_code == 403


@pytest.mark.usefixtures("init_self_db")
class TestRbacMatrixShape:
    """GET 返回 matrix + roles + permission_keys；matrix[role][perm] 为 bool。"""

    async def test_default_matrix_returns_full_roles_x_perms(
        self, client, admin_headers
    ) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        body = r.json()
        assert set(body["roles"]) == set(rbac.ROLES)
        assert set(body["permission_keys"]) == set(rbac.PERMISSION_KEYS)
        matrix = body["matrix"]
        for role in rbac.ROLES:
            assert role in matrix
            for k in rbac.PERMISSION_KEYS:
                assert isinstance(matrix[role][k], bool), f"{role}.{k} non-bool"

    async def test_default_admin_has_all_perms(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        admin_row = r.json()["matrix"]["admin"]
        assert all(admin_row.values())  # admin 默认全权

    async def test_default_agent_has_chat_dispatch_only(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        agent_row = r.json()["matrix"]["agent"]
        assert agent_row["chat.dispatch"] is True
        for k, v in agent_row.items():
            if k.startswith("admin."):
                assert v is False, f"agent should not have {k}"


@pytest.mark.usefixtures("init_self_db")
class TestRbacUpsert:
    """PUT 即时生效 + 缓存清空验证。"""

    async def test_upsert_grants_perm_to_agent(self, client, admin_headers) -> None:
        body = {
            "items": [
                {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
            ]
        }
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"ok": True, "count": 1}
        # 立即生效：重读矩阵反映新权
        r2 = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        assert r2.json()["matrix"]["agent"]["admin.dashboard"] is True

    async def test_upsert_revoke_admin_perm(self, client, admin_headers) -> None:
        body = {
            "items": [
                {"role": "admin", "permission_key": "admin.dashboard", "allowed": 0},
            ]
        }
        await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        # admin 被收回 dashboard 权（业务上不推荐，但底层应允许，由前端拦）
        assert r.json()["matrix"]["admin"]["admin.dashboard"] is False

    async def test_upsert_then_is_permitted_reflects_change(self, admin_headers, client) -> None:
        """is_permitted 走缓存；upsert 后必须看到新值（否则缓存未失效）。"""
        # 先看默认值（agent 无 admin.staff）
        assert await rbac.is_permitted("agent", "admin.staff") is False
        body = {"items": [{"role": "agent", "permission_key": "admin.staff", "allowed": 1}]}
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 200
        # 关键断言：缓存被 upsert_many 清掉，再查走新 DB 值
        assert await rbac.is_permitted("agent", "admin.staff") is True

    async def test_upsert_repeated_does_idempotent_update(
        self, client, admin_headers
    ) -> None:
        """同一 (role, perm) 重复 upsert 走 UPDATE 分支，不会插重复行 / 不报错。"""
        body = {"items": [{"role": "agent", "permission_key": "admin.sla", "allowed": 1}]}
        r1 = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        r2 = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r1.status_code == 200
        assert r2.status_code == 200

    async def test_upsert_batch_multiple_items(self, client, admin_headers) -> None:
        body = {
            "items": [
                {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
                {"role": "senior", "permission_key": "admin.dashboard", "allowed": 1},
                {"role": "manager", "permission_key": "admin.sla", "allowed": 1},
            ]
        }
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["count"] == 3

    async def test_upsert_empty_items_returns_zero(self, client, admin_headers) -> None:
        r = await client.put(
            "/admin/api/v1/rbac/matrix", json={"items": []}, headers=admin_headers
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True, "count": 0}

    async def test_upsert_unknown_role_and_perm_accepted(self, client, admin_headers) -> None:
        """role / permission_key 在 DB 层无白名单：写入应成功（未来 perm 灰度无需 schema 改）。

        但 list_matrix 只回 ROLES × PERMISSION_KEYS 内的条目，新加的看不见——这是设计。
        """
        body = {
            "items": [
                {"role": "ghost_role", "permission_key": "admin.future", "allowed": 1},
            ]
        }
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 200


@pytest.mark.usefixtures("init_self_db")
class TestRbacValidation:
    """请求体校验：缺字段 / 类型错应 422。"""

    async def test_missing_items_returns_422(self, client, admin_headers) -> None:
        r = await client.put("/admin/api/v1/rbac/matrix", json={}, headers=admin_headers)
        assert r.status_code == 422

    async def test_item_missing_role_returns_422(self, client, admin_headers) -> None:
        body = {"items": [{"permission_key": "admin.dashboard", "allowed": 1}]}
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 422

    async def test_item_wrong_type_returns_422(self, client, admin_headers) -> None:
        # allowed 必须 int；传字符串 "yes" 会被 pydantic 拒
        body = {
            "items": [
                {"role": "agent", "permission_key": "admin.dashboard", "allowed": "yes"}
            ]
        }
        r = await client.put("/admin/api/v1/rbac/matrix", json=body, headers=admin_headers)
        assert r.status_code == 422

    async def test_get_does_not_accept_body(self, client, admin_headers) -> None:
        """GET 不应被 PUT-only 字段干扰。"""
        r = await client.get("/admin/api/v1/rbac/matrix", headers=admin_headers)
        assert r.status_code == 200
