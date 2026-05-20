async def test_mode_default_ai(temp_db_url):
    from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="c", subject_id="U1")
    mode, staff = await get_mode(cid)
    assert mode == "ai"
    assert staff is None

    await set_mode(cid, "human_takeover", "S100")
    mode, staff = await get_mode(cid)
    assert mode == "human_takeover"
    assert staff == "S100"


async def test_set_mode_rejects_invalid(temp_db_url):
    import pytest

    from ai_engine.persistence.conversations import create_conversation, set_mode
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="c", subject_id="U1")
    with pytest.raises(ValueError):
        await set_mode(cid, "bogus")


async def test_list_for_staff_filters_non_ai(temp_db_url):
    from ai_engine.persistence.conversations import (
        append_human_message,
        create_conversation,
        list_for_staff,
        set_mode,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    c1 = await create_conversation(user_type="c", subject_id="U1")
    await create_conversation(user_type="c", subject_id="U2")  # stays ai
    await set_mode(c1, "human_pending")
    await append_human_message(c1, sender_staff_id="S100", content="您好，我来接手")

    pending = await list_for_staff("human_pending")
    assert [c["id"] for c in pending] == [c1]
    assert await list_for_staff("all")  # 非 ai 的都在


async def test_staff_crud(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import authenticate, create_staff

    await init_db()
    sid = await create_staff("S100", "张三", "agent", "secret123")
    assert sid

    s = await authenticate("S100", "secret123")
    assert s and s["display_name"] == "张三"
    assert await authenticate("S100", "wrong") is None
    assert await authenticate("nobody", "x") is None
