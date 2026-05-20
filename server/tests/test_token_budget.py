from unittest.mock import AsyncMock, MagicMock


async def test_under_limit_records_and_allows(temp_db_url, monkeypatch):
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1000")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence.db import init_db

    await init_db()
    allowed, info = await check_and_record("b", "BU1", 100, 50)
    assert allowed is True
    assert info["used"] == 150
    assert info["warn"] is False


async def test_warn_at_80_percent(temp_db_url, monkeypatch):
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1000")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence.db import init_db

    await init_db()
    await check_and_record("b", "BU1", 800, 0)
    allowed, info = await check_and_record("b", "BU1", 10, 0)
    assert allowed is True
    assert info["warn"] is True


async def test_over_limit_refuses_and_does_not_record(temp_db_url, monkeypatch):
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1000")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance.token_budget import _get_used, check_and_record
    from ai_engine.persistence.db import init_db

    await init_db()
    from datetime import UTC, datetime

    await check_and_record("b", "BU1", 1000, 0)  # 打满
    allowed, _ = await check_and_record("b", "BU1", 50, 50)
    assert allowed is False
    # 拒服不记账：用量仍是 1000
    today = datetime.now(UTC).date().isoformat()
    used_in, used_out = await _get_used("BU1", "b", today)
    assert used_in + used_out == 1000


async def test_isolated_by_subject(temp_db_url, monkeypatch):
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1000")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence.db import init_db

    await init_db()
    await check_and_record("b", "BU1", 1000, 0)
    allowed, _ = await check_and_record("b", "BU2", 10, 0)
    assert allowed is True


async def test_runtime_refuses_when_over_budget(seeded_db, monkeypatch):
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent import runtime
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.integrations import anthropic_client as ac

    # 先打满额度
    await check_and_record("b", "BU00243780", 5, 0)

    fake = MagicMock()
    fake.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(type="text", text="回复")],
            stop_reason="end_turn",
            usage=MagicMock(input_tokens=1, output_tokens=1),
        )
    )
    monkeypatch.setattr(ac, "_client", fake)

    events = []
    async for ev in runtime.run_turn(
        conversation_id=1, user_type="b", subject_id="BU00243780", user_message="问"
    ):
        events.append(ev)

    assert any(e["type"] == "system" and "额度已用完" in e["text"] for e in events)
    # 拒服后没有正常文本回复
    assert not any(e["type"] == "text" for e in events)
