from ai_engine.persistence import routing_rules


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    routing_rules.invalidate_cache()


async def test_crud(temp_db_url):
    await _init(temp_db_url)
    rid = await routing_rules.create_rule("user_type", "c", 100, priority=10)
    rows = await routing_rules.list_rules()
    assert len(rows) == 1 and rows[0]["id"] == rid
    await routing_rules.set_active(rid, 0)
    assert int((await routing_rules.list_rules())[0]["active"]) == 0


async def test_match_by_user_type(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("user_type", "b", 7, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text=None
    )
    assert gid == 7


async def test_match_keyword(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("keyword", "卡片", 9, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="c", last_user_text="我想问卡片申请"
    )
    assert gid == 9


async def test_priority_first_wins(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("user_type", "b", 5, priority=10)
    await routing_rules.create_rule("keyword", "订单", 8, priority=5)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text="订单问题"
    )
    assert gid == 8


async def test_no_match_returns_none(temp_db_url):
    await _init(temp_db_url)
    await routing_rules.create_rule("user_type", "c", 7, priority=10)
    gid = await routing_rules.match_for_conversation(
        user_type="b", last_user_text="xxx"
    )
    assert gid is None
