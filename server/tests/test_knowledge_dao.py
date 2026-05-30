from ai_engine.persistence import knowledge


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_publish_get(temp_db_url):
    await _init(temp_db_url)
    eid = await knowledge.upsert_entry(
        type_="error_code", key="E1001", title="登录失败",
        content="账号或密码错误", locale="zh", created_by="EN1",
    )
    await knowledge.publish(eid)
    row = await knowledge.get_published(type_="error_code", key="E1001", locale="zh")
    assert row is not None and row["title"] == "登录失败"


async def test_upsert_updates_existing(temp_db_url):
    await _init(temp_db_url)
    e1 = await knowledge.upsert_entry(
        type_="faq", key="login_help", title="登录指南", content="v1", locale="zh", created_by="EN1",
    )
    e2 = await knowledge.upsert_entry(
        type_="faq", key="login_help", title="登录指南", content="v2", locale="zh", created_by="EN1",
    )
    assert e1 == e2


async def test_list_by_type_filter(temp_db_url):
    await _init(temp_db_url)
    await knowledge.upsert_entry(
        type_="error_code", key="E1", title="t1", content="c1", locale="zh", created_by="EN1",
    )
    await knowledge.upsert_entry(
        type_="faq", key="f1", title="t2", content="c2", locale="zh", created_by="EN1",
    )
    rows = await knowledge.list_entries(type_="error_code")
    assert len(rows) == 1 and rows[0]["key"] == "E1"


async def test_get_published_misses_draft_only(temp_db_url):
    await _init(temp_db_url)
    await knowledge.upsert_entry(
        type_="api_doc", key="/users", title="x", content="y", locale="zh", created_by="EN1",
    )
    row = await knowledge.get_published(type_="api_doc", key="/users", locale="zh")
    assert row is None
