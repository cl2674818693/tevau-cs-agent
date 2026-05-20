from httpx import ASGITransport, AsyncClient


async def test_user_message_in_human_takeover_skips_agent(temp_db_url, monkeypatch):
    """human_takeover 模式下，用户发消息只入库 + 推客服侧，不调 LLM。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings

    settings.reload()

    from ai_engine.persistence.conversations import create_conversation, list_messages, set_mode
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="b", subject_id="BU00243780")
    await set_mode(cid, "human_takeover", "S100")

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={cid}&message=我的卡为啥被锁",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            lines = [line async for line in resp.aiter_lines()]

    # 不应调 AI：无 tool_use、无 message_start
    assert not any("event: tool_use" in line for line in lines)
    assert not any("event: message_start" in line for line in lines)
    # 应告知已转人工
    assert any("event: mode_change" in line for line in lines)
    assert any("handed_to_human" in line for line in lines)
    # 用户消息已落库
    msgs = await list_messages(cid)
    assert any(m["role"] == "user" and "锁" in m["content"] for m in msgs)


async def test_ai_mode_still_runs_agent(temp_db_url, monkeypatch):
    """ai 模式下仍走正常 agent loop（用 mock client）。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.agent import runtime
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    cid = await create_conversation(user_type="b", subject_id="BU00243780")

    async def fake_run_turn(**kwargs):
        yield {"type": "text", "text": "正常回复"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={cid}&message=hi",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            lines = [line async for line in resp.aiter_lines()]

    assert any("event: message_start" in line for line in lines)
    assert any("正常回复" in line for line in lines)
