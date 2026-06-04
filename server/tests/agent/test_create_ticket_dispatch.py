import pytest

from ai_engine.agent.tools import create_ticket
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db, rbac, staff_presence
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str


@pytest.fixture
async def db_ready(temp_db_url):
    rbac.invalidate_cache()
    await init_db()
    return temp_db_url


async def _seed_staff(staff_id: str, role: str = "agent"):
    await db.execute(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, created_at) "
        "VALUES (:i, :n, :r, '', :now) ON CONFLICT(staff_id) DO UPDATE SET role=:r",
        {"i": staff_id, "n": staff_id, "r": role, "now": now_str()},
    )
    await staff_presence.heartbeat(staff_id, "online")


@pytest.mark.asyncio
async def test_ensure_human_pending_no_one_online(db_ready):
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    info = await create_ticket._ensure_human_pending(cid)
    assert info == {"no_one_online": True}
    mode, _ = await conv_dao.get_mode(cid)
    assert mode == "human_pending"


@pytest.mark.asyncio
async def test_ensure_human_pending_dispatched(db_ready):
    await _seed_staff("A")
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    info = await create_ticket._ensure_human_pending(cid)
    assert info == {"no_one_online": False}


@pytest.mark.asyncio
async def test_ensure_human_pending_returns_no_off_hours_field(db_ready):
    """旧的 off_hours / next_shift_start 字段必须删干净。"""
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    info = await create_ticket._ensure_human_pending(cid)
    assert "off_hours" not in info
    assert "next_shift_start" not in info
