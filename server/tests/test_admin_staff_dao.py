from ai_engine.persistence import staff as staff_mod


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_list_staff(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.create_staff("AD1", "管理员", "admin", "x")
    rows = await staff_mod.list_staff()
    ids = {r["staff_id"] for r in rows}
    assert ids == {"AG1", "AD1"}
    assert all("password_hash" not in r for r in rows)  # 不泄露密码


async def test_update_staff_role_and_name(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.update_staff("AG1", display_name="高级客服", role="senior")
    row = await staff_mod.get_staff("AG1")
    assert row["display_name"] == "高级客服"
    assert row["role"] == "senior"


async def test_update_staff_partial_keeps_other(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "x")
    await staff_mod.update_staff("AG1", role="supervisor")  # 只改角色
    row = await staff_mod.get_staff("AG1")
    assert row["display_name"] == "客服一"  # 名字保留
    assert row["role"] == "supervisor"


async def test_set_active_and_reset_password(temp_db_url):
    await _init(temp_db_url)
    await staff_mod.create_staff("AG1", "客服一", "agent", "oldpw")
    await staff_mod.set_staff_active("AG1", 0)
    assert int((await staff_mod.get_staff("AG1"))["active"]) == 0
    await staff_mod.reset_staff_password("AG1", "newpw")
    await staff_mod.set_staff_active("AG1", 1)
    assert await staff_mod.authenticate("AG1", "newpw") is not None
    assert await staff_mod.authenticate("AG1", "oldpw") is None
