"""客服组 /admin/api/v1/staff-groups。

被测：admin_staff_groups CRUD。
覆盖：鉴权（supervisor + admin 通过；其他 403）；create + list；
     重名 (UNIQUE INDEX ux_staff_group_name) → 端点捕获转 409（修复 source bug #3）；
     patch name / description / active；patch 不存在 ID → 404（修复 bug #5）；
     delete 不存在 ID → 404（修复 bug #6）；
     delete 时级联清空 staff.group_id 引用（修复 bug #7）；
     422 缺字段。
"""

import pytest


@pytest.mark.usefixtures("init_self_db")
class TestGroupsAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/admin/api/v1/staff-groups"),
            ("POST", "/admin/api/v1/staff-groups"),
            ("PATCH", "/admin/api/v1/staff-groups/1"),
            ("DELETE", "/admin/api/v1/staff-groups/1"),
        ],
    )
    async def test_no_token_returns_401(self, client, method: str, path: str) -> None:
        kw = {}
        if method == "POST":
            kw = {"json": {"name": "g"}}
        elif method == "PATCH":
            kw = {"json": {"name": "new"}}
        r = await client.request(method, path, **kw)
        assert r.status_code == 401

    @pytest.mark.parametrize("role", ["agent", "senior", "engineer", "manager"])
    async def test_non_sup_admin_forbidden(
        self, client, auth_headers, role: str
    ) -> None:
        r = await client.get("/admin/api/v1/staff-groups", headers=auth_headers(role))
        assert r.status_code == 403

    async def test_supervisor_pass(self, client, supervisor_headers) -> None:
        r = await client.get(
            "/admin/api/v1/staff-groups", headers=supervisor_headers
        )
        assert r.status_code == 200


@pytest.mark.usefixtures("init_self_db")
class TestGroupsCrud:
    async def test_list_empty(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"groups": []}

    async def test_create_minimal(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "支付组"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["id"], int)

    async def test_create_with_description(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "风控组", "description": "处理风控类工单"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (
            await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        ).json()["groups"]
        assert rows[0]["name"] == "风控组"
        assert rows[0]["description"] == "处理风控类工单"
        assert int(rows[0]["active"]) == 1

    async def test_create_missing_name_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff-groups", json={}, headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_create_duplicate_name_returns_409(
        self, client, admin_headers
    ) -> None:
        """同名组：UNIQUE INDEX 由端点捕获并转 409（bug #3 已修）。"""
        await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "dup"},
            headers=admin_headers,
        )
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "dup"},
            headers=admin_headers,
        )
        assert r.status_code == 409


@pytest.mark.usefixtures("init_self_db")
class TestGroupsPatch:
    async def _create(self, client, admin_headers, name: str = "g1") -> int:
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": name},
            headers=admin_headers,
        )
        return int(r.json()["id"])

    async def test_patch_name(self, client, admin_headers) -> None:
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}",
            json={"name": "g_renamed"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (
            await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        ).json()["groups"]
        assert rows[0]["name"] == "g_renamed"

    async def test_patch_description_only(self, client, admin_headers) -> None:
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}",
            json={"description": "desc"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (
            await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        ).json()["groups"]
        assert rows[0]["description"] == "desc"
        assert rows[0]["name"] == "g1"  # 未传字段保留

    async def test_patch_disable(self, client, admin_headers) -> None:
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}",
            json={"active": 0},
            headers=admin_headers,
        )
        assert r.status_code == 200
        rows = (
            await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        ).json()["groups"]
        assert int(rows[0]["active"]) == 0

    async def test_patch_combined(self, client, admin_headers) -> None:
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}",
            json={"name": "x", "description": "y", "active": 0},
            headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_patch_empty_body_is_noop_200(
        self, client, admin_headers
    ) -> None:
        """空 body 且 group 存在：API 不强制至少一个字段（与 shifts 不同）→ 200 noop。"""
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}", json={}, headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_patch_empty_body_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """空 body 但 group_id 不存在：仍应 404（不能让 noop 掩盖存在性 bug）。"""
        r = await client.patch(
            "/admin/api/v1/staff-groups/999999", json={}, headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_patch_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """对不存在的 group_id patch：rowcount=0 → 404（bug #5 已修）。"""
        r = await client.patch(
            "/admin/api/v1/staff-groups/999999",
            json={"name": "ghost"},
            headers=admin_headers,
        )
        assert r.status_code == 404


@pytest.mark.usefixtures("init_self_db")
class TestGroupsDelete:
    async def test_delete_removes(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "to_del"},
            headers=admin_headers,
        )
        gid = r.json()["id"]
        r2 = await client.delete(
            f"/admin/api/v1/staff-groups/{gid}", headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}
        rows = (
            await client.get("/admin/api/v1/staff-groups", headers=admin_headers)
        ).json()["groups"]
        assert rows == []

    async def test_delete_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """DELETE 不存在 ID：rowcount=0 → 404（bug #6 已修）。"""
        r = await client.delete(
            "/admin/api/v1/staff-groups/999999", headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_delete_does_cascade_staff_group_id(
        self, client, admin_headers
    ) -> None:
        """删组后引用该组的 staff.group_id 应被级联清空为 NULL（bug #7 已修）。
        DAO 在事务内先 UPDATE staff SET group_id=NULL 再 DELETE，避免孤儿引用。
        """
        # 建组 + 一个绑定该组的客服
        r = await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "g"},
            headers=admin_headers,
        )
        gid = r.json()["id"]
        await client.post(
            "/admin/api/v1/staff",
            json={"staff_id": "m1", "display_name": "M",
                  "role": "agent", "password": "pw"},
            headers=admin_headers,
        )
        await client.patch(
            "/admin/api/v1/staff/m1",
            json={"group_id": gid},
            headers=admin_headers,
        )
        # 删组
        await client.delete(
            f"/admin/api/v1/staff-groups/{gid}", headers=admin_headers,
        )
        # 客服的 group_id 已被清空
        rows = (await client.get("/admin/api/v1/staff", headers=admin_headers)).json()["staff"]
        m1 = next(x for x in rows if x["staff_id"] == "m1")
        assert m1["group_id"] is None
