from ai_engine.persistence import rbac


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    rbac.invalidate_cache()


async def test_default_admin_has_all(temp_db_url):
    await _init(temp_db_url)
    assert await rbac.is_permitted("admin", "admin.dashboard") is True
    assert await rbac.is_permitted("admin", "admin.cost") is True


async def test_default_agent_has_none(temp_db_url):
    await _init(temp_db_url)
    assert await rbac.is_permitted("agent", "admin.dashboard") is False


async def test_db_overrides_default(temp_db_url):
    await _init(temp_db_url)
    await rbac.upsert_many("AD1", [
        {"role": "agent", "permission_key": "admin.dashboard", "allowed": 1},
    ])
    assert await rbac.is_permitted("agent", "admin.dashboard") is True


async def test_list_matrix_combines_default_and_db(temp_db_url):
    await _init(temp_db_url)
    await rbac.upsert_many("AD1", [
        {"role": "supervisor", "permission_key": "admin.cost", "allowed": 1},
    ])
    matrix = await rbac.list_matrix()
    assert matrix["admin"]["admin.dashboard"] is True
    assert matrix["supervisor"]["admin.cost"] is True
    assert matrix["supervisor"]["admin.qa"] is True
