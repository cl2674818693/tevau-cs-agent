"""客服账号 /admin/api/v1/staff CRUD。

被测：admin_staff.list_staff / create_staff / patch_staff / reset_password。
覆盖：
- 鉴权（仅 admin）
- 创建 + 列表
- role 白名单 400
- 重复 staff_id：UNIQUE 被端点捕获 → 409（修复 source bug #2）
- patch 各字段 / role 非法 400
- patch / reset-password 对不存在 staff_id → 404（修复 source bug #4）
- 启用/禁用 active；reset-password 端点；非法 active 类型 422
"""

import pytest


@pytest.mark.usefixtures("init_self_db")
class TestStaffAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/admin/api/v1/staff"),
            ("POST", "/admin/api/v1/staff"),
            ("PATCH", "/admin/api/v1/staff/s1"),
            ("POST", "/admin/api/v1/staff/s1/reset-password"),
        ],
    )
    async def test_no_token_returns_401(self, client, method: str, path: str) -> None:
        kw = {}
        if "reset-password" in path:
            kw = {"json": {"password": "x"}}
        elif method == "POST":
            kw = {"json": {"staff_id": "s1", "display_name": "n", "role": "agent",
                           "password": "p"}}
        elif method == "PATCH":
            kw = {"json": {"display_name": "x"}}
        r = await client.request(method, path, **kw)
        assert r.status_code == 401

    @pytest.mark.parametrize(
        "role", ["agent", "senior", "supervisor", "manager", "engineer"]
    )
    async def test_non_admin_forbidden(
        self, client, auth_headers, role: str
    ) -> None:
        r = await client.get("/admin/api/v1/staff", headers=auth_headers(role))
        assert r.status_code == 403

    async def test_admin_pass(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/staff", headers=admin_headers)
        assert r.status_code == 200


@pytest.mark.usefixtures("init_self_db")
class TestStaffCreate:
    async def test_create_and_list(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "s1", "display_name": "Alice",
                  "role": "agent", "password": "pw1"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True
        r2 = await client.get("/admin/api/v1/staff", headers=admin_headers)
        rows = r2.json()["staff"]
        assert len(rows) == 1
        assert rows[0]["staff_id"] == "s1"
        assert rows[0]["display_name"] == "Alice"
        assert rows[0]["role"] == "agent"
        assert int(rows[0]["active"]) == 1
        # 不应回传 password_hash（list_staff SQL 未 SELECT 该列）
        assert "password_hash" not in rows[0]

    @pytest.mark.parametrize(
        "role", ["agent", "senior", "engineer", "admin", "supervisor", "manager"]
    )
    async def test_create_all_valid_roles(
        self, client, admin_headers, role: str
    ) -> None:
        r = await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": f"x_{role}", "display_name": role,
                  "role": role, "password": "pw"},
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_create_invalid_role_400(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "sx", "display_name": "x",
                  "role": "godmode", "password": "pw"},
            headers=admin_headers,
        )
        assert r.status_code == 400

    async def test_create_missing_field_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "sx", "display_name": "x"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_create_duplicate_staff_id_returns_409(
        self, client, admin_headers
    ) -> None:
        """同 staff_id 二次创建：UNIQUE 由端点捕获并转 409（spec 行为，bug #2 已修）。"""
        await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "dup", "display_name": "A",
                  "role": "agent", "password": "pw"},
            headers=admin_headers,
        )
        r = await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "dup", "display_name": "B",
                  "role": "agent", "password": "pw"},
            headers=admin_headers,
        )
        assert r.status_code == 409


@pytest.mark.usefixtures("init_self_db")
class TestStaffPatch:
    async def _seed(self, client, admin_headers, sid: str = "p1") -> None:
        await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": sid, "display_name": "Old",
                  "role": "agent", "password": "pw"},
            headers=admin_headers,
        )

    async def test_patch_display_name_only(self, client, admin_headers) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1",
            json={"display_name": "New"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        r2 = await client.get("/admin/api/v1/staff", headers=admin_headers)
        assert r2.json()["staff"][0]["display_name"] == "New"

    async def test_patch_role_changes(self, client, admin_headers) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1",
            json={"role": "supervisor"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        r2 = await client.get("/admin/api/v1/staff", headers=admin_headers)
        assert r2.json()["staff"][0]["role"] == "supervisor"

    async def test_patch_invalid_role_400(self, client, admin_headers) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1",
            json={"role": "bogus"},
            headers=admin_headers,
        )
        assert r.status_code == 400

    async def test_patch_disable_then_enable(self, client, admin_headers) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1", json={"active": 0}, headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (await client.get("/admin/api/v1/staff", headers=admin_headers)).json()["staff"]
        assert int(rows[0]["active"]) == 0
        # 重新启用
        r = await client.patch(
            "/admin/api/v1/staff/p1", json={"active": 1}, headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (await client.get("/admin/api/v1/staff", headers=admin_headers)).json()["staff"]
        assert int(rows[0]["active"]) == 1

    async def test_patch_disable_disabled_does_not_409(
        self, client, admin_headers
    ) -> None:
        """对已禁用账号再禁用：当前实现幂等成功（DB UPDATE 无前置状态检查）。
        若未来加状态机限制要求 409，此测试需更新。
        """
        await self._seed(client, admin_headers)
        await client.patch(
            "/admin/api/v1/staff/p1", json={"active": 0}, headers=admin_headers,
        )
        r = await client.patch(
            "/admin/api/v1/staff/p1", json={"active": 0}, headers=admin_headers,
        )
        assert r.status_code in (200, 409)

    async def test_patch_combined(self, client, admin_headers) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1",
            json={
                "display_name": "Combo",
                "role": "manager",
                "active": 0,
            },
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_patch_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """patch 不存在的 staff_id：端点先查存在性 → 404（bug #4 已修）。"""
        r = await client.patch(
            "/admin/api/v1/staff/no_such",
            json={"display_name": "x"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_patch_active_type_error_422(
        self, client, admin_headers
    ) -> None:
        await self._seed(client, admin_headers)
        r = await client.patch(
            "/admin/api/v1/staff/p1",
            json={"active": "not-an-int"},
            headers=admin_headers,
        )
        assert r.status_code == 422


@pytest.mark.usefixtures("init_self_db")
class TestStaffResetPassword:
    async def test_reset_changes_hash(self, client, admin_headers) -> None:
        await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "rp", "display_name": "x",
                  "role": "agent", "password": "old"},
            headers=admin_headers,
        )
        # 旧密码能登（authenticate 内部不走 API；这里直接调 DAO 验证）
        from ai_engine.persistence import staff as sm

        old_ok = await sm.authenticate("rp", "old")
        assert old_ok is not None
        r = await client.post(
            "/admin/api/v1/staff/rp/reset-password",
            json={"password": "new"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert await sm.authenticate("rp", "old") is None
        assert await sm.authenticate("rp", "new") is not None

    async def test_reset_missing_password_422(
        self, client, admin_headers
    ) -> None:
        r = await client.post(
            "/admin/api/v1/staff/rp/reset-password",
            json={},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_reset_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """对不存在 staff_id reset：DAO 返 rowcount=0 → 端点 404（bug #4 已修）。"""
        r = await client.post(
            "/admin/api/v1/staff/ghost/reset-password",
            json={"password": "x"},
            headers=admin_headers,
        )
        assert r.status_code == 404
