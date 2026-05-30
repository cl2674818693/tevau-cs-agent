from ai_engine.persistence import guardrails


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    guardrails.invalidate_cache()


async def test_blocklist_subject(temp_db_url):
    await _init(temp_db_url)
    await guardrails.create_rule("blocklist", "BAD_USER_1", "block", "EN1")
    result = await guardrails.evaluate("BAD_USER_1", "c", "随便什么文字")
    assert result == ("block", "blocklist:BAD_USER_1")


async def test_sensitive_word_flag(temp_db_url):
    await _init(temp_db_url)
    await guardrails.create_rule("sensitive_word", "敏感词", "flag", "EN1")
    result = await guardrails.evaluate("USER1", "c", "这里包含 敏感词 内容")
    assert result == ("flag", "sensitive_word:敏感词")


async def test_no_rule_allows(temp_db_url):
    await _init(temp_db_url)
    result = await guardrails.evaluate("USER1", "c", "正常内容")
    assert result == ("allow", None)


async def test_inactive_rule_ignored(temp_db_url):
    await _init(temp_db_url)
    rid = await guardrails.create_rule("blocklist", "BAD", "block", "EN1")
    await guardrails.set_active(rid, 0)
    result = await guardrails.evaluate("BAD", "c", "x")
    assert result == ("allow", None)
