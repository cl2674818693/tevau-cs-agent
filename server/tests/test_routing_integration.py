"""路由匹配落 target_group_id 集成验证。"""


async def test_route_conversation_writes_target_group(temp_db_url):
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (1, 'c', 'u1', 'human_pending', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, status, created_at) "
        "VALUES (1, 'user', '我想问卡片的事', 'done', '2026-06-01 00:00:01')"
    )
    await routing_rules.create_rule("keyword", "卡片", target_group_id=7, priority=10)
    gid = await routing_rules.route_conversation_now(conv_id=1, user_type="c")
    assert gid == 7
    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = 1", {}
    )
    assert int(row["target_group_id"]) == 7


async def test_route_no_match_sets_null(temp_db_url):
    from ai_engine.persistence import db, routing_rules
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (2, 'b', 'BU1', 'human_pending', '2026-06-01 00:00:00')"
    )
    await db.execute(
        "INSERT INTO messages(conversation_id, role, content, status, created_at) "
        "VALUES (2, 'user', '不相关的内容', 'done', '2026-06-01 00:00:01')"
    )
    await routing_rules.create_rule("user_type", "c", target_group_id=7, priority=10)
    gid = await routing_rules.route_conversation_now(conv_id=2, user_type="b")
    assert gid is None
    row = await db.fetch_one(
        "SELECT target_group_id FROM conversations WHERE id = 2", {}
    )
    assert row["target_group_id"] is None
