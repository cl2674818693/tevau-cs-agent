from ai_engine.persistence import prompt_drafts


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()


async def test_create_and_list(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "reply_style.c.md", "你好世界", "EN1")
    rows = await prompt_drafts.list_by_version("v2.0.0")
    assert len(rows) == 1 and rows[0]["id"] == did
    assert rows[0]["status"] == "draft"


async def test_publish_then_get(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "reply_style.c.md", "正式版本", "EN1")
    await prompt_drafts.publish(did, "EN1")
    p = await prompt_drafts.get_published("v2.0.0", "reply_style.c.md")
    assert p is not None and p["content"] == "正式版本"


async def test_get_published_returns_latest(temp_db_url):
    await _init(temp_db_url)
    d1 = await prompt_drafts.create_draft("v2.0.0", "a.md", "v1", "EN1")
    await prompt_drafts.publish(d1, "EN1")
    d2 = await prompt_drafts.create_draft("v2.0.0", "a.md", "v2", "EN1")
    await prompt_drafts.publish(d2, "EN1")
    p = await prompt_drafts.get_published("v2.0.0", "a.md")
    assert p["content"] == "v2"


async def test_delete_draft(temp_db_url):
    await _init(temp_db_url)
    did = await prompt_drafts.create_draft("v2.0.0", "a.md", "x", "EN1")
    await prompt_drafts.delete_draft(did)
    assert await prompt_drafts.list_by_version("v2.0.0") == []


async def test_get_published_none_when_missing(temp_db_url):
    await _init(temp_db_url)
    assert await prompt_drafts.get_published("v1.0.0", "nope.md") is None
