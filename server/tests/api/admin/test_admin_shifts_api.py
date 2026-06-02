"""排班 API /admin/api/v1/shifts。

被测：admin_shifts.list_shifts / create_shift / patch_shift / delete_shift。
覆盖：鉴权矩阵；CRUD happy path；空表；按 staff_id / 时间窗过滤；
     limit 边界 (ge=1, le=1000) → 422；patch 不传字段 → 400；patch 不存在 → 404；
     跨日排班；删除幂等。
"""

import pytest


@pytest.mark.usefixtures("init_self_db")
class TestShiftsAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/admin/api/v1/shifts"),
            ("POST", "/admin/api/v1/shifts"),
            ("PATCH", "/admin/api/v1/shifts/1"),
            ("DELETE", "/admin/api/v1/shifts/1"),
        ],
    )
    async def test_no_token_returns_401(self, client, method: str, path: str) -> None:
        kw = {"json": {"staff_id": "x", "start_at": "2025-01-01 00:00:00",
                       "end_at": "2025-01-01 08:00:00"}} if method == "POST" else {}
        if method == "PATCH":
            kw = {"json": {"staff_id": "x"}}
        r = await client.request(method, path, **kw)
        assert r.status_code == 401

    @pytest.mark.parametrize("role", ["agent", "senior", "engineer", "manager"])
    async def test_non_sup_admin_forbidden_list(
        self, client, auth_headers, role: str
    ) -> None:
        r = await client.get("/admin/api/v1/shifts", headers=auth_headers(role))
        assert r.status_code == 403

    async def test_supervisor_pass(self, client, supervisor_headers) -> None:
        r = await client.get("/admin/api/v1/shifts", headers=supervisor_headers)
        assert r.status_code == 200

    async def test_admin_pass(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/shifts", headers=admin_headers)
        assert r.status_code == 200


@pytest.mark.usefixtures("init_self_db")
class TestShiftsList:
    async def test_empty_list(self, client, admin_headers) -> None:
        r = await client.get("/admin/api/v1/shifts", headers=admin_headers)
        assert r.status_code == 200
        assert r.json() == {"shifts": []}

    async def test_list_returns_inserted(self, client, admin_headers) -> None:
        await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-06-01 09:00:00",
                  "end_at": "2025-06-01 18:00:00"},
            headers=admin_headers,
        )
        r = await client.get("/admin/api/v1/shifts", headers=admin_headers)
        rows = r.json()["shifts"]
        assert len(rows) == 1
        assert rows[0]["staff_id"] == "s1"
        assert rows[0]["start_at"] == "2025-06-01 09:00:00"

    async def test_filter_by_staff_id(self, client, admin_headers) -> None:
        for sid in ("s1", "s2", "s2", "s3"):
            await client.post(
                "/admin/api/v1/shifts",
                json={"staff_id": sid, "start_at": "2025-06-01 09:00:00",
                      "end_at": "2025-06-01 18:00:00"},
                headers=admin_headers,
            )
        r = await client.get(
            "/admin/api/v1/shifts",
            headers=admin_headers,
            params={"staff_id": "s2"},
        )
        rows = r.json()["shifts"]
        assert len(rows) == 2
        assert all(x["staff_id"] == "s2" for x in rows)

    async def test_filter_by_time_window(self, client, admin_headers) -> None:
        await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-05-30 09:00:00",
                  "end_at": "2025-05-30 18:00:00"},
            headers=admin_headers,
        )
        await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-06-10 09:00:00",
                  "end_at": "2025-06-10 18:00:00"},
            headers=admin_headers,
        )
        r = await client.get(
            "/admin/api/v1/shifts",
            headers=admin_headers,
            params={"from": "2025-06-01 00:00:00", "to": "2025-06-30 23:59:59"},
        )
        rows = r.json()["shifts"]
        assert len(rows) == 1
        assert rows[0]["start_at"].startswith("2025-06-10")

    async def test_cross_day_shift_stored_verbatim(
        self, client, admin_headers
    ) -> None:
        """跨日班次（夜班）：字符串原样存储/返回；list 不做时区/跨日特殊处理。"""
        await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "night", "start_at": "2025-06-01 22:00:00",
                  "end_at": "2025-06-02 06:00:00"},
            headers=admin_headers,
        )
        r = await client.get(
            "/admin/api/v1/shifts",
            headers=admin_headers,
            params={"staff_id": "night"},
        )
        row = r.json()["shifts"][0]
        assert row["start_at"] == "2025-06-01 22:00:00"
        assert row["end_at"] == "2025-06-02 06:00:00"

    @pytest.mark.parametrize("limit", [0, -1, 1001])
    async def test_limit_out_of_range_422(
        self, client, admin_headers, limit: int
    ) -> None:
        r = await client.get(
            "/admin/api/v1/shifts",
            headers=admin_headers,
            params={"limit": limit},
        )
        assert r.status_code == 422

    async def test_limit_caps_results(self, client, admin_headers) -> None:
        for i in range(5):
            await client.post(
                "/admin/api/v1/shifts",
                json={"staff_id": f"s{i}",
                      "start_at": f"2025-06-0{i + 1} 09:00:00",
                      "end_at": f"2025-06-0{i + 1} 18:00:00"},
                headers=admin_headers,
            )
        r = await client.get(
            "/admin/api/v1/shifts",
            headers=admin_headers,
            params={"limit": 3},
        )
        assert len(r.json()["shifts"]) == 3


@pytest.mark.usefixtures("init_self_db")
class TestShiftsCreate:
    async def test_create_returns_id(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-06-01 09:00:00",
                  "end_at": "2025-06-01 18:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert isinstance(body["id"], int) and body["id"] > 0

    async def test_create_missing_field_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-06-01 09:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    async def test_create_wrong_type_422(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": 123, "start_at": None, "end_at": []},
            headers=admin_headers,
        )
        assert r.status_code == 422


@pytest.mark.usefixtures("init_self_db")
class TestShiftsPatch:
    async def _create(self, client, admin_headers) -> int:
        r = await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "s1", "start_at": "2025-06-01 09:00:00",
                  "end_at": "2025-06-01 18:00:00"},
            headers=admin_headers,
        )
        return int(r.json()["id"])

    async def test_patch_single_field(self, client, admin_headers) -> None:
        sid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/shifts/{sid}",
            json={"end_at": "2025-06-01 20:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["end_at"] == "2025-06-01 20:00:00"
        assert r.json()["start_at"] == "2025-06-01 09:00:00"  # 未传字段不变

    async def test_patch_multi_fields(self, client, admin_headers) -> None:
        sid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/shifts/{sid}",
            json={"staff_id": "s9", "start_at": "2025-06-02 10:00:00",
                  "end_at": "2025-06-02 19:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["staff_id"] == "s9"
        assert body["start_at"] == "2025-06-02 10:00:00"
        assert body["end_at"] == "2025-06-02 19:00:00"

    async def test_patch_no_fields_returns_400(self, client, admin_headers) -> None:
        sid = await self._create(client, admin_headers)
        r = await client.patch(
            f"/admin/api/v1/shifts/{sid}", json={}, headers=admin_headers,
        )
        assert r.status_code == 400

    async def test_patch_nonexistent_returns_404(self, client, admin_headers) -> None:
        r = await client.patch(
            "/admin/api/v1/shifts/999999",
            json={"end_at": "2099-01-01 00:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 404

    async def test_patch_invalid_id_path_422(self, client, admin_headers) -> None:
        r = await client.patch(
            "/admin/api/v1/shifts/not-an-int",
            json={"end_at": "2099-01-01 00:00:00"},
            headers=admin_headers,
        )
        assert r.status_code == 422


@pytest.mark.usefixtures("init_self_db")
class TestShiftsDelete:
    async def test_delete_removes_row(self, client, admin_headers) -> None:
        r = await client.post(
            "/admin/api/v1/shifts",
            json={"staff_id": "sd", "start_at": "2025-06-01 09:00:00",
                  "end_at": "2025-06-01 18:00:00"},
            headers=admin_headers,
        )
        sid = r.json()["id"]
        r2 = await client.delete(
            f"/admin/api/v1/shifts/{sid}", headers=admin_headers,
        )
        assert r2.status_code == 200
        assert r2.json() == {"ok": True}
        r3 = await client.get("/admin/api/v1/shifts", headers=admin_headers)
        assert r3.json()["shifts"] == []

    async def test_delete_nonexistent_returns_404(
        self, client, admin_headers
    ) -> None:
        """DELETE 不存在 ID：DAO 返 rowcount=0 → 端点 404（bug #6 已修）。"""
        r = await client.delete(
            "/admin/api/v1/shifts/999999", headers=admin_headers,
        )
        assert r.status_code == 404
