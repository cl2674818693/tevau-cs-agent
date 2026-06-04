import pytest

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db, rbac, staff_presence
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str
from ai_engine.services import dispatch


@pytest.fixture
async def db_ready(temp_db_url):
    rbac.invalidate_cache()
    await init_db()
    return temp_db_url


async def _seed_staff(staff_id: str, role: str = "agent"):
    """直接写 staff 表 + presence 表 + 心跳"""
    await db.execute(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, created_at) "
        "VALUES (:i, :n, :r, '', :now) ON CONFLICT(staff_id) DO UPDATE SET role=:r",
        {"i": staff_id, "n": staff_id, "r": role, "now": now_str()},
    )
    await staff_presence.heartbeat(staff_id, "online")


@pytest.mark.asyncio
async def test_dispatch_picks_least_loaded(db_ready):
    # A:2 在聊  B:0  C:1 → 应选 B
    await _seed_staff("A")
    await _seed_staff("B")
    await _seed_staff("C")
    for sid, loads in [("A", 2), ("C", 1)]:
        for _ in range(loads):
            cid = await conv_dao.create_conversation(user_type="c", subject_id="x")
            await db.execute(
                "UPDATE conversations SET mode='human_takeover', "
                "assigned_staff_id=:s, assigned_at=:t WHERE id=:c",
                {"s": sid, "t": now_str(), "c": cid},
            )

    new_cid = await conv_dao.create_conversation(user_type="c", subject_id="user-x")
    await conv_dao.set_mode(new_cid, "human_pending")

    result = await dispatch.dispatch_to_human_pending(new_cid)
    assert result["dispatched"] is True
    assert result["staff_id"] == "B"

    row = await db.fetch_one(
        "SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": new_cid}
    )
    assert row["assigned_staff_id"] == "B"


@pytest.mark.asyncio
async def test_dispatch_no_one_online_returns_flag(db_ready):
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    result = await dispatch.dispatch_to_human_pending(cid)
    assert result == {"dispatched": False, "no_one_online": True}


@pytest.mark.asyncio
async def test_dispatch_excludes_role_without_chat_dispatch(db_ready):
    await _seed_staff("eng", role="engineer")
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    result = await dispatch.dispatch_to_human_pending(cid)
    assert result["dispatched"] is False
    assert result["no_one_online"] is True


@pytest.mark.asyncio
async def test_dispatch_excludes_stale_heartbeat(db_ready):
    await _seed_staff("zombie")
    await db.execute(
        "UPDATE staff_presence SET last_seen_at=:t WHERE staff_id='zombie'",
        {"t": "2026-01-01 00:00:00"},
    )
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    result = await dispatch.dispatch_to_human_pending(cid)
    assert result["dispatched"] is False
    assert result["no_one_online"] is True


@pytest.mark.asyncio
async def test_dispatch_pending_assignments_count_as_load(db_ready):
    """已派给 A 但未接管的会话也算 A 的 load，否则连续派单都派给同一人。"""
    await _seed_staff("A")
    await _seed_staff("B")
    # A 已派 1 个未接管（human_pending + assigned_staff_id），B 啥也没
    pending_to_a = await conv_dao.create_conversation(user_type="c", subject_id="x")
    await db.execute(
        "UPDATE conversations SET mode='human_pending', "
        "assigned_staff_id='A', assigned_at=:t WHERE id=:c",
        {"t": now_str(), "c": pending_to_a},
    )

    # 新会话派单应该选 B（A.load=1, B.load=0）
    new_cid = await conv_dao.create_conversation(user_type="c", subject_id="user-y")
    await conv_dao.set_mode(new_cid, "human_pending")
    result = await dispatch.dispatch_to_human_pending(new_cid)

    assert result["dispatched"] is True
    assert result["staff_id"] == "B"


@pytest.mark.asyncio
async def test_dispatch_idempotent_when_already_assigned(db_ready):
    """已经派给某人后再次调 dispatch，不应覆盖。"""
    await _seed_staff("A")
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await conv_dao.set_mode(cid, "human_pending")
    await db.execute(
        "UPDATE conversations SET assigned_staff_id='already', assigned_at=:t WHERE id=:c",
        {"t": now_str(), "c": cid},
    )

    result = await dispatch.dispatch_to_human_pending(cid)
    assert result["dispatched"] is False
    assert result.get("already_assigned") is True
    row = await db.fetch_one("SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": cid})
    assert row["assigned_staff_id"] == "already"
