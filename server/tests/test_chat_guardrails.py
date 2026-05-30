"""验证 guardrails.evaluate 接入两处入口：

- POST /api/v1/conversations（init）：按 subject_id 拦 blocklist
- GET /api/v1/chat（SSE stream）：按消息文本拦 sensitive_word（流内 error_event + stop）
"""

_H_BAD = {"X-BU-ID": "BU_BAD"}
_H_OK = {"X-BU-ID": "BU_OK"}


async def _seed_rules():
    from ai_engine.persistence import guardrails

    guardrails.invalidate_cache()
    await guardrails.create_rule("blocklist", "BU_BAD", "block", "EN1")
    await guardrails.create_rule("sensitive_word", "诈骗", "block", "EN1")


async def test_init_blocklist_subject_403(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.db import init_db

    await init_db()
    await _seed_rules()

    from httpx import ASGITransport, AsyncClient

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/conversations", json={"resume": None}, headers=_H_BAD
        )
    assert r.status_code == 403
    from ai_engine.persistence import guardrails

    guardrails.invalidate_cache()


async def test_init_normal_subject_passes(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.db import init_db

    await init_db()
    await _seed_rules()

    from httpx import ASGITransport, AsyncClient

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/conversations", json={"resume": None}, headers=_H_OK
        )
    assert r.status_code == 200
    from ai_engine.persistence import guardrails

    guardrails.invalidate_cache()


async def test_chat_sensitive_word_blocks_stream(temp_db_url, monkeypatch):
    """消息含敏感词：stream 内 error_event + message_stop(guardrail_blocked)，不调 LLM。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "x")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.db import init_db

    await init_db()
    await _seed_rules()
    cid = await create_conversation(user_type="b", subject_id="BU_OK")

    from httpx import ASGITransport, AsyncClient

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={cid}&message=这是诈骗信息",
            headers=_H_OK,
        ) as resp:
            lines = [line async for line in resp.aiter_lines()]
    assert any("guardrail_blocked" in line for line in lines)
    assert not any("event: tool_use" in line for line in lines)
    from ai_engine.persistence import guardrails

    guardrails.invalidate_cache()
