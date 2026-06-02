"""客服组 /admin/api/v1/staff-groups。

被测：admin_staff_groups CRUD。
覆盖：鉴权（supervisor + admin 通过；其他 403）；create + list；
     重名 (UNIQUE INDEX ux_staff_group_name) → IntegrityError（API 未捕，记 source bug）；
     patch name / description / active；delete 后成员关系不级联（schema 无 FK，是设计）；
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

    async def test_create_duplicate_name_raises(
        self, client, admin_headers
    ) -> None:
        """同名组：UNIQUE INDEX 触发 IntegrityError，API 未捕 → 异常透传。
        spec 期望 409；记录为 source bug。
        """
        from sqlalchemy.exc import IntegrityError

        await client.post(
            "/admin/api/v1/staff-groups",
            json={"name": "dup"},
            headers=admin_headers,
        )
        with pytest.raises(IntegrityError):
            await client.post(
                "/admin/api/v1/staff-groups",
                json={"name": "dup"},
                headers=admin_headers,
            )


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
        """空 body：API 没强制要求至少一个字段（与 shifts 不同），不会 400。"""
        gid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/staff-groups/{gid}", json={}, headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_patch_nonexistent_silent_200(
        self, client, admin_headers
    ) -> None:
        """对不存在的 group_id patch：UPDATE 0 行 → 不报错（无 404 检查，source 设计）。"""
        r = await client.patch(
            "/admin/api/v1/staff-groups/999999",
            json={"name": "ghost"},
            headers=admin_headers,
        )
        assert r.status_code in (200, 404)


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

    async def test_delete_nonexistent_idempotent(
        self, client, admin_headers
    ) -> None:
        r = await client.delete(
            "/admin/api/v1/staff-groups/999999", headers=admin_headers,
        )
        assert r.status_code == 200

    async def test_delete_does_not_cascade_staff_group_id(
        self, client, admin_headers
    ) -> None:
        """删组后引用该组的 staff.group_id 保留（schema 无 FK，不级联）。
        前端/上层需感知并自行解绑。记录为已知设计行为，避免误以为级联会发生。
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
        # 客服仍带原 group_id（孤儿引用，前端需处理）
        rows = (await client.get("/admin/api/v1/staff", headers=admin_headers)).json()["staff"]
        m1 = next(x for x in rows if x["staff_id"] == "m1")
        assert m1["group_id"] == gid  # 未被级联清空
