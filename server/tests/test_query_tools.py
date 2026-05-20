async def test_query_user_returns_only_subject_bu(seeded_db):
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U1")
    assert out["user"]["email"] == "a@x.com"


async def test_query_user_rejects_cross_bu(seeded_db):
    from ai_engine.agent.tools.query_user import run

    out = await run(bu_id="BU00243780", user_id="U2")  # U2 属于 BU_OTHER
    assert out["user"] is None
    assert "not found" in out["note"].lower() or "not in" in out["note"].lower()


async def test_query_card_returns_lock_reason(seeded_db):
    from ai_engine.agent.tools.query_card import run

    out = await run(bu_id="BU00243780", card_id="4938750672464590")
    assert out["card"]["status"] == "locked"
    assert "R-217" in out["card"]["lock_reason"]


async def test_query_api_call_by_uid(seeded_db):
    from ai_engine.agent.tools.query_api_call import run

    out = await run(bu_id="BU00243780", uid="1765348436409")
    assert out["call"]["status_code"] == 500
    assert out["call"]["error_code"] == "DB_TIMEOUT"
