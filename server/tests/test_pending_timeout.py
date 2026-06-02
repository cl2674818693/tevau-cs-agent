"""转人工超时推事项中心：sweep 命中 sla_policies.take_time 阈值后推一次，且按会话去重。"""

import pytest

from ai_engine.persistence import db
from ai_engine.persistence.db import init_db


async def _seed_pending_conv(created_at: str = "2000-01-01 00:00:00") -> int:
    """造一条 mode=human_pending 的会话，created_at 默认放到很久以前以触发超时。"""
    return await db.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, mode, created_at) "
        "VALUES ('c', 'u1', 'human_pending', :ts) RETURNING id",
        {"ts": created_at},
    )


@pytest.fixture
def captured_pushes(monkeypatch):
    """拦截 push_event_center，收集 payload；默认返回 True。"""
    pushes: list[dict] = []

    async def _fake_push(payload):
        pushes.append(payload)
        return True

    import ai_engine.persistence.maintenance as m

    monkeypatch.setattr(m, "push_event_center", _fake_push)
    return pushes


async def test_pushes_when_take_time_breached(temp_db_url, captured_pushes):
    await init_db()
    from ai_engine.persistence import admin_sla
    from ai_engine.persistence.maintenance import push_pending_takeover_timeouts

    conv_id = await _seed_pending_conv()
    await admin_sla.create_policy("take_time", 60, "all", None)

    n = await push_pending_takeover_timeouts()
    assert n == 1
    assert len(captured_pushes) == 1
    p = captured_pushes[0]
    assert p["type"] == "pending_takeover_timeout"
    assert p["conversation_id"] == conv_id
    assert p["threshold_seconds"] == 60
    assert p["elapsed_seconds"] > 60
    assert p["user_type"] == "c"
    assert p["subject_id"] == "u1"


async def test_dedup_does_not_push_twice(temp_db_url, captured_pushes):
    await init_db()
    from ai_engine.persistence import admin_sla
    from ai_engine.persistence.maintenance import push_pending_takeover_timeouts

    await _seed_pending_conv()
    await admin_sla.create_policy("take_time", 60, "all", None)

    assert await push_pending_takeover_timeouts() == 1
    assert await push_pending_takeover_timeouts() == 0
    assert len(captured_pushes) == 1


async def test_not_pushed_when_under_threshold(temp_db_url, captured_pushes):
    await init_db()
    from ai_engine.persistence import admin_sla
    from ai_engine.persistence.maintenance import push_pending_takeover_timeouts

    # created_at = 现在附近；但 compute_breaches 用 _elapsed = now - created_at，
    # 我们用一个不可能超过的大阈值，确保不命中
    from ai_engine.persistence.schema import now_str

    await _seed_pending_conv(now_str())
    await admin_sla.create_policy("take_time", 999999, "all", None)

    assert await push_pending_takeover_timeouts() == 0
    assert captured_pushes == []


async def test_no_policy_means_no_push(temp_db_url, captured_pushes):
    await init_db()
    from ai_engine.persistence.maintenance import push_pending_takeover_timeouts

    await _seed_pending_conv()
    # 没有 take_time 策略
    assert await push_pending_takeover_timeouts() == 0
    assert captured_pushes == []


async def test_skip_already_taken_over(temp_db_url, captured_pushes):
    """已被接管的会话（有 staff_actions.action='take'）不推超时。"""
    await init_db()
    from ai_engine.persistence import admin_sla
    from ai_engine.persistence.maintenance import push_pending_takeover_timeouts
    from ai_engine.persistence.schema import now_str

    conv_id = await _seed_pending_conv()
    await db.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:cid, 's1', 'take', :at)",
        {"cid": conv_id, "at": now_str()},
    )
    # 同时把 mode 切到 human_takeover（贴近真实）
    await db.execute(
        "UPDATE conversations SET mode='human_takeover' WHERE id=:id", {"id": conv_id}
    )
    await admin_sla.create_policy("take_time", 60, "all", None)

    assert await push_pending_takeover_timeouts() == 0
    assert captured_pushes == []


async def test_push_failure_does_not_dedup(temp_db_url, monkeypatch):
    """推送失败时不写去重表，下次扫描可重试。"""
    await init_db()
    import ai_engine.persistence.maintenance as m
    from ai_engine.persistence import admin_sla

    attempts = {"n": 0}

    async def _flaky(payload):
        attempts["n"] += 1
        return attempts["n"] >= 2  # 第二次才成功

    monkeypatch.setattr(m, "push_event_center", _flaky)

    await _seed_pending_conv()
    await admin_sla.create_policy("take_time", 60, "all", None)

    assert await m.push_pending_takeover_timeouts() == 0  # 第一次推失败，不计入
    assert await m.push_pending_takeover_timeouts() == 1  # 第二次推成功
    assert await m.push_pending_takeover_timeouts() == 0  # 已去重
