from ai_engine.persistence.staff import create_staff, get_staff


async def test_create_supervisor_and_manager(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    await create_staff("SUP1", "主管", "supervisor", "x")
    await create_staff("MGR1", "老板", "manager", "x")
    assert (await get_staff("SUP1"))["role"] == "supervisor"
    assert (await get_staff("MGR1"))["role"] == "manager"


async def test_create_rejects_unknown_role(temp_db_url):
    from ai_engine.persistence.db import init_db

    await init_db()
    import pytest

    with pytest.raises(ValueError):
        await create_staff("X1", "x", "ceo", "x")
