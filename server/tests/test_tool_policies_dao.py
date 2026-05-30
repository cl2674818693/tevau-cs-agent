from ai_engine.persistence import tool_policies


async def _init(temp_db_url):
    from ai_engine.persistence.db import init_db
    await init_db()
    tool_policies.invalidate_cache()


async def test_default_fallback_when_empty(temp_db_url):
    """表空时：受 STAFF 默认白名单覆盖的工具+角色返回 True，其它返回 False。"""
    await _init(temp_db_url)
    # 既有默认：query_user 在 _STAFF_TOOL_WHITELIST；agent 允许调
    assert await tool_policies.is_tool_allowed("query_user", "agent") is True
    # 不在白名单的随便起名字 → False
    assert await tool_policies.is_tool_allowed("dangerous_tool", "agent") is False


async def test_default_unmask_for_engineer(temp_db_url):
    await _init(temp_db_url)
    assert await tool_policies.is_unmask_allowed("query_user", "engineer") is True
    assert await tool_policies.is_unmask_allowed("query_user", "agent") is False


async def test_db_overrides_default(temp_db_url):
    await _init(temp_db_url)
    # 写一行：禁用 query_user / agent
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "agent",
         "allowed": 0, "unmask_allowed": 0},
    ])
    assert await tool_policies.is_tool_allowed("query_user", "agent") is False


async def test_list_all_returns_db_rows(temp_db_url):
    await _init(temp_db_url)
    await tool_policies.upsert_many("AD1", [
        {"tool_name": "query_user", "role": "senior",
         "allowed": 1, "unmask_allowed": 1},
    ])
    rows = await tool_policies.list_all()
    assert len(rows) == 1 and rows[0]["tool_name"] == "query_user"
    assert int(rows[0]["unmask_allowed"]) == 1
