import pytest

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db
from ai_engine.persistence.db import init_db
from ai_engine.persistence import rbac
from ai_engine.services import dispatch


@pytest.fixture
async def db_ready(temp_db_url):
    rbac.invalidate_cache()
    await init_db()
    return temp_db_url


@pytest.mark.asyncio
async def test_watcher_clears_timed_out_assignments(db_ready):
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    await db.execute(
        "UPDATE conversations SET assigned_staff_id='stale', assigned_at='2026-01-01 00:00:00' "
        "WHERE id=:c",
        {"c": cid},
    )

    released_ids = await dispatch._scan_and_clear_timeouts()
    assert cid in released_ids
    row = await db.fetch_one(
        "SELECT assigned_staff_id, assigned_at FROM conversations WHERE id=:c", {"c": cid}
    )
    assert row["assigned_staff_id"] is None
    assert row["assigned_at"] is None


@pytest.mark.asyncio
async def test_watcher_keeps_recent_assignments(db_ready):
    from ai_engine.persistence.schema import now_str

    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    await db.execute(
        "UPDATE conversations SET assigned_staff_id='fresh', assigned_at=:t WHERE id=:c",
        {"t": now_str(), "c": cid},
    )

    released = await dispatch._scan_and_clear_timeouts()
    assert cid not in released


@pytest.mark.asyncio
async def test_watcher_ignores_human_takeover(db_ready):
    """已 takeover 的不应被 watcher 误清"""
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await db.execute(
        "UPDATE conversations SET mode='human_takeover', "
        "assigned_staff_id='X', assigned_at='2026-01-01 00:00:00' WHERE id=:c",
        {"c": cid},
    )
    released = await dispatch._scan_and_clear_timeouts()
    assert cid not in released
    row = await db.fetch_one("SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": cid})
    assert row["assigned_staff_id"] == "X"
