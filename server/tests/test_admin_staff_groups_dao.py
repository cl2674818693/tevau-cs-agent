import json

from ai_engine.persistence import admin_staff_groups
from ai_engine.persistence import staff as staff_mod


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_group_crud(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("证券组", "处理证券类问题")
    rows = await admin_staff_groups.list_groups()
    assert len(rows) == 1 and rows[0]["id"] == gid
    assert rows[0]["name"] == "证券组"


async def test_group_name_unique(temp_db_url):
    await _init(temp_db_url)
    await admin_staff_groups.create_group("证券组", None)
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await admin_staff_groups.create_group("证券组", None)


async def test_set_staff_group_and_skills(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("证券组", None)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.set_staff_group("AG1", gid)
    await staff_mod.set_staff_skills("AG1", ["c", "stock"])
    rows = await staff_mod.list_staff()
    row = next(r for r in rows if r["staff_id"] == "AG1")
    assert int(row["group_id"]) == gid
    assert json.loads(row["skills"]) == ["c", "stock"]


async def test_set_staff_group_none_clears(temp_db_url):
    await _init(temp_db_url)
    gid = await admin_staff_groups.create_group("g", None)
    await staff_mod.create_staff("AG1", "x", "agent", "x")
    await staff_mod.set_staff_group("AG1", gid)
    await staff_mod.set_staff_group("AG1", None)
    row = next(r for r in await staff_mod.list_staff() if r["staff_id"] == "AG1")
    assert row["group_id"] is None
