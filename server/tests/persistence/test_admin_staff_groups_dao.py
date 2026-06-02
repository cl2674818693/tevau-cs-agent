"""Persistence: admin_staff_groups.py — 客服分组 CRUD（含唯一 name 索引）。"""

import pytest

from ai_engine.persistence import admin_staff_groups as g
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestCreateGroup:
    async def test_create_returns_pk(self, db_ready) -> None:
        gid = await g.create_group("一线客服", "处理 C 端")
        assert gid > 0

    async def test_duplicate_name_raises(self, db_ready) -> None:
        """ux_staff_group_name UNIQUE 约束。"""
        await g.create_group("一线", None)
        with pytest.raises(Exception):  # noqa: B017 unique constraint
            await g.create_group("一线", None)

    async def test_null_description(self, db_ready) -> None:
        await g.create_group("一线", None)
        rows = await g.list_groups()
        assert rows[0]["description"] is None


class TestListGroups:
    async def test_ordered_by_id(self, db_ready) -> None:
        await g.create_group("B", None)
        await g.create_group("A", None)
        rows = await g.list_groups()
        assert [r["name"] for r in rows] == ["B", "A"]

    async def test_active_only(self, db_ready) -> None:
        gid_active = await g.create_group("active", None)
        gid_inactive = await g.create_group("inactive", None)
        await g.set_group_active(gid_inactive, 0)
        rows = await g.list_groups(active_only=True)
        ids = {r["id"] for r in rows}
        assert gid_active in ids and gid_inactive not in ids

    async def test_empty(self, db_ready) -> None:
        assert await g.list_groups() == []


class TestUpdateGroup:
    async def test_update_name(self, db_ready) -> None:
        gid = await g.create_group("old", "desc")
        await g.update_group(gid, name="new")
        rows = await g.list_groups()
        assert rows[0]["name"] == "new"
        assert rows[0]["description"] == "desc"  # 保留

    async def test_update_description(self, db_ready) -> None:
        gid = await g.create_group("g1", "old desc")
        await g.update_group(gid, description="new desc")
        rows = await g.list_groups()
        assert rows[0]["description"] == "new desc"

    async def test_update_both_none_noop(self, db_ready) -> None:
        gid = await g.create_group("g1", "desc")
        await g.update_group(gid)
        rows = await g.list_groups()
        assert rows[0]["name"] == "g1"
        assert rows[0]["description"] == "desc"


class TestSetGroupActive:
    async def test_toggle(self, db_ready) -> None:
        gid = await g.create_group("g1", None)
        await g.set_group_active(gid, 0)
        rows = await g.list_groups()
        assert rows[0]["active"] == 0
        await g.set_group_active(gid, 1)
        rows = await g.list_groups()
        assert rows[0]["active"] == 1


class TestDeleteGroup:
    async def test_delete(self, db_ready) -> None:
        gid = await g.create_group("g1", None)
        await g.delete_group(gid)
        assert await g.list_groups() == []

    async def test_delete_missing_no_error(self, db_ready) -> None:
        await g.delete_group(99999)
