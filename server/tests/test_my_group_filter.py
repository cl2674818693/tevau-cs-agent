import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings
    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import admin_staff_groups, db
    from ai_engine.persistence.staff import create_staff, set_staff_group

    g1 = await admin_staff_groups.create_group("证券组", None)
    await create_staff("AG1", "客服1", "agent", "x")
    await set_staff_group("AG1", g1)
    await db.execute(
        f"INSERT INTO conversations(id, user_type, subject_id, mode, target_group_id, "
        f"created_at) VALUES (1, 'b', 'BU1', 'human_pending', {g1}, '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (2, 'b', 'BU2', 'human_pending', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, target_group_id, "
        "created_at) VALUES (3, 'b', 'BU3', 'human_pending', 9999, '2026-06-01 00:00:00')"
    )
    yield {"ag": issue_staff_token("AG1", "agent")}
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_my_group_only_filters(env):
    """my_group_only=true 时 AG1 只看到本组(A)和无定向(B)。"""
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get(
            "/staff/api/v1/conversations?my_group_only=true",
            headers=_h(env["ag"]),
        )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json()}
    assert 1 in ids and 2 in ids
    assert 3 not in ids


async def test_without_filter_sees_all(env):
    from ai_engine import main as main_mod
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.get(
            "/staff/api/v1/conversations",
            headers=_h(env["ag"]),
        )
    assert r.status_code == 200
    ids = {it["id"] for it in r.json()}
    assert {1, 2, 3} <= ids
