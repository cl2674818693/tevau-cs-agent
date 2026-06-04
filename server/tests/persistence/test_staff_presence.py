import pytest

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db, staff_presence
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.mark.asyncio
async def test_release_pending_assignments_releases_pending_only(db_ready):
    cid_pending_1 = await conv_dao.create_conversation(user_type="c", subject_id="u1")
    cid_pending_2 = await conv_dao.create_conversation(user_type="c", subject_id="u2")
    cid_takeover = await conv_dao.create_conversation(user_type="c", subject_id="u3")
    sid = "staff-A"

    await db.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id=:s, "
        "assigned_at=:t WHERE id IN (:a, :b)",
        {"s": sid, "t": now_str(), "a": cid_pending_1, "b": cid_pending_2},
    )
    await db.execute(
        "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:s, "
        "assigned_at=:t WHERE id=:c",
        {"s": sid, "t": now_str(), "c": cid_takeover},
    )

    released = await staff_presence.release_pending_assignments(sid)

    assert sorted(released) == sorted([cid_pending_1, cid_pending_2])
    row = await db.fetch_one(
        "SELECT mode, assigned_staff_id FROM conversations WHERE id=:c",
        {"c": cid_takeover},
    )
    assert row["mode"] == "human_takeover"
    assert row["assigned_staff_id"] == sid


@pytest.mark.asyncio
async def test_release_pending_assignments_empty_returns_empty_list(db_ready):
    assert await staff_presence.release_pending_assignments("nobody") == []
