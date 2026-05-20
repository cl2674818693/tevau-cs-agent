async def test_init_creates_tables(temp_db_url):
    from ai_engine.persistence.db import get_conn, init_db

    await init_db()
    async with get_conn() as conn:
        rows = await (
            await conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        ).fetchall()
    names = {r[0] for r in rows}
    assert {"conversations", "messages", "tool_audits", "tickets", "ticket_events"} <= names


async def test_create_and_get_conversation(temp_db_url):
    from ai_engine.persistence.conversations import create_conversation, get_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    conv_id = await create_conversation(user_type="b", subject_id="BU00243780")
    conv = await get_conversation(conv_id)
    assert conv["user_type"] == "b"
    assert conv["subject_id"] == "BU00243780"


async def test_append_and_list_messages(temp_db_url):
    from ai_engine.persistence.conversations import (
        append_message,
        create_conversation,
        list_messages,
    )
    from ai_engine.persistence.db import init_db

    await init_db()
    conv_id = await create_conversation(user_type="b", subject_id="BU00243780")
    await append_message(conv_id, role="user", content="hi")
    await append_message(conv_id, role="assistant", content="hello")
    msgs = await list_messages(conv_id)
    assert [m["role"] for m in msgs] == ["user", "assistant"]


async def test_audit_log_tool_call(temp_db_url):
    from ai_engine.persistence.audit import list_audits, log_tool_call
    from ai_engine.persistence.db import init_db

    await init_db()
    await log_tool_call(
        conversation_id=1,
        tool_name="search_code",
        params={"repo": "openapi_backend", "query": "card_bind"},
        result_size=2048,
        duration_ms=42,
        rejected=False,
        reject_reason=None,
    )
    rows = await list_audits(conversation_id=1)
    assert len(rows) == 1 and rows[0]["tool_name"] == "search_code"


async def test_ticket_crud(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import append_ticket_event, create_ticket, get_ticket

    await init_db()
    ext_id = "AI-2026-05-18-7a3f1c"
    await create_ticket(external_id=ext_id, conversation_id=1, payload={"category": "bug"})
    await append_ticket_event(ext_id, event="assigned", actor="嘉豪", comment="ok")
    t = await get_ticket(ext_id)
    assert t["events"][-1]["event"] == "assigned"


async def test_ticket_severity_override(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket, get_ticket, update_ticket_severity

    await init_db()
    ext_id = "AI-2026-05-18-sev"
    await create_ticket(
        external_id=ext_id, conversation_id=1, payload={"category": "bug", "severity": "p2"}
    )
    await update_ticket_severity(external_id=ext_id, severity="p0")
    t = await get_ticket(ext_id)
    assert t["current_severity"] == "p0"
