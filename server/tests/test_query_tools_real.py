async def test_query_user_returns_masked_data(business_mysql):
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U1")
    u = out["user"]
    assert u["email"] == "al***@x.com"
    assert u["phone"] == "138****78"
    assert u["bu_id"] == "BU00243780"


async def test_query_user_rejects_cross_bu(business_mysql):
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U2")  # U2 属于 BU_OTHER
    assert out["user"] is None


async def test_query_card_masks_card_no_and_lock_reason(business_mysql):
    from ai_engine.agent.tools.query_card import run

    out = await run(bu_id="BU00243780", card_id="C100")
    c = out["card"]
    assert "R-217" not in c["lock_reason"]
    assert c["card_no"] == "4938 **** **** 4590"


async def test_query_api_call_by_uid(business_mysql):
    from ai_engine.agent.tools.query_api_call import run

    out = await run(bu_id="BU00243780", uid="1765348436409")
    assert out["call"]["status_code"] == 500
