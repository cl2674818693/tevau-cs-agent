"""create_ticket 工具 category=人工介入 时同步切 conversation.mode=human_pending。

行为对齐 /request-human 端点：保证 AI 主动建工单转人工时，admin "会话"列表
也能筛出来（默认筛 mode!=ai）。否则会话停在 mode=ai，客服看不到待接管。
"""

import pytest


async def _seed_conv(user_type: str = "c", subject_id: str = "U1", mode: str = "ai") -> int:
    from ai_engine.persistence import db
    from ai_engine.persistence.schema import now_str

    cid = await db.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES (:ut, :sid, :m, :now) RETURNING id",
        {"ut": user_type, "sid": subject_id, "m": mode, "now": now_str()},
    )
    return cid


@pytest.fixture
def _no_event_center(monkeypatch):
    monkeypatch.setenv("EVENT_CENTER_URL", "http://ec.invalid")
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "test")
    from ai_engine.config import settings

    settings.reload()


async def test_human_intervention_switches_mode_to_pending(temp_db_url, _no_event_center):
    from ai_engine.agent.tools.create_ticket import run
    from ai_engine.persistence import conversations as conv_dao
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await _seed_conv(mode="ai")

    out = await run(
        subject_id="U1",
        user_type="c",
        conversation_id=cid,
        category="人工介入",
        summary="用户请求人工：xxx",
        severity="p2",
        evidence={"conversation_id": cid},
    )
    assert out["external_ticket_id"].startswith("AI-")
    mode, _ = await conv_dao.get_mode(cid)
    assert mode == "human_pending"


async def test_non_human_intervention_does_not_switch_mode(temp_db_url, _no_event_center):
    from ai_engine.agent.tools.create_ticket import run
    from ai_engine.persistence import conversations as conv_dao
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await _seed_conv(mode="ai")

    await run(
        subject_id="U1",
        user_type="c",
        conversation_id=cid,
        category="bug",
        summary="AI 答错",
        severity="p2",
        evidence={"conversation_id": cid},
    )
    mode, _ = await conv_dao.get_mode(cid)
    assert mode == "ai"  # 非人工介入类工单不切 mode


async def test_human_intervention_when_already_takeover(temp_db_url, _no_event_center):
    """已 human_takeover 时不重切（避免覆盖 assigned_staff_id 和误触 mode_change）。"""
    from ai_engine.agent.tools.create_ticket import run
    from ai_engine.persistence import conversations as conv_dao
    from ai_engine.persistence.db import init_db, get_conn

    await init_db()
    cid = await _seed_conv(mode="ai")
    # 模拟已接管
    from sqlalchemy import text

    async with get_conn() as conn:
        await conn.execute(
            text(
                "UPDATE conversations SET mode='human_takeover', assigned_staff_id='admin' "
                "WHERE id=:id"
            ),
            {"id": cid},
        )

    await run(
        subject_id="U1",
        user_type="c",
        conversation_id=cid,
        category="人工介入",
        summary="再次请求",
        severity="p2",
        evidence={"conversation_id": cid},
    )
    mode, sid = await conv_dao.get_mode(cid)
    assert mode == "human_takeover"
    assert sid == "admin"
