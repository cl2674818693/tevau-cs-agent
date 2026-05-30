"""验证转人工时自动调 routing_rules.route_conversation_now 落 target_group_id。

实际转人工端点在 user_events.py 的 POST /api/v1/conversations/{id}/request-human
（plan 里假设的 /handoff 路径不存在）。
"""

_H = {"X-BU-ID": "BU00243780"}


async def test_request_human_writes_target_group(temp_db_url, monkeypatch):
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import create_ticket as ct
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.conversations import append_message, create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    routing_rules.invalidate_cache()

    # 路由规则：keyword "卡片" → group 7
    await db.execute(
        "INSERT INTO staff_groups(id, name, created_at) "
        "VALUES (7, '卡片组', '2026-06-01 00:00:00')"
    )
    await routing_rules.create_rule(
        match_type="keyword", match_value="卡片", target_group_id=7, priority=10
    )

    cid = await create_conversation(user_type="b", subject_id="BU00243780")
    await append_message(cid, role="user", content="我想问卡片申请")

    # mock create_ticket 的外部 HTTP
    async def fake_post(url, json, headers):
        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(ct, "_post", fake_post)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/v1/conversations/{cid}/request-human",
            json={"reason": "AI 答非所问"},
            headers=_H,
        )
    assert r.status_code == 200

    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = :id", {"id": cid}
    )
    assert int(row["target_group_id"]) == 7

    routing_rules.invalidate_cache()


async def test_request_human_no_rule_match_leaves_null(temp_db_url, monkeypatch):
    """没规则命中：target_group_id 仍为 NULL，端点照样 200。"""
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import create_ticket as ct
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.conversations import append_message, create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    routing_rules.invalidate_cache()

    cid = await create_conversation(user_type="b", subject_id="BU00243780")
    await append_message(cid, role="user", content="完全无关的消息")

    async def fake_post(url, json, headers):
        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(ct, "_post", fake_post)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/v1/conversations/{cid}/request-human",
            json={"reason": "x"},
            headers=_H,
        )
    assert r.status_code == 200

    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = :id", {"id": cid}
    )
    assert row["target_group_id"] is None

    routing_rules.invalidate_cache()
