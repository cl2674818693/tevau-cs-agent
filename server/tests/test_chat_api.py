from httpx import ASGITransport, AsyncClient


async def test_chat_endpoint_streams_events(seeded_db, monkeypatch):
    """SSE 主链路：conversation → message_start → content_block_delta... → message_stop。

    runtime 流出领域事件（text/tool_call），chat.py 映射成 spec §3.3 wire 事件。
    """
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime

    async def fake_run_turn(**kwargs):
        yield {"type": "text", "text": "你好"}
        yield {"type": "text", "text": "！"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init = await client.post(
            "/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"}
        )
        conv_id = init.json()["conversation_id"]
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={conv_id}&message=hi",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            assert resp.status_code == 200
            chunks = [line async for line in resp.aiter_lines()]
    assert any("event: conversation" in line for line in chunks)
    assert any("content_block_delta" in line for line in chunks)
    assert any("你好" in line for line in chunks)
    assert any("message_stop" in line for line in chunks)


async def test_chat_rate_limited_after_threshold(seeded_db, monkeypatch):
    """spec §6.4 兜底层：单 subject 超过每分钟阈值后返回 RATE_LIMITED。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CHAT_RATE_LIMIT_PER_MIN", "2")
    from ai_engine import main as main_mod
    from ai_engine.agent import runtime
    from ai_engine.config import settings
    from ai_engine.governance import rate_limit

    settings.reload()
    rate_limit.reset()

    async def fake_run_turn(**kwargs):
        yield {"type": "text", "text": "ok"}

    monkeypatch.setattr(runtime, "run_turn", fake_run_turn)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init = await client.post("/api/v1/conversations", json={}, headers={"X-BU-ID": "BU_RL"})
        conv_id = init.json()["conversation_id"]

        async def send() -> list[str]:
            async with client.stream(
                "GET",
                f"/api/v1/chat?conversation_id={conv_id}&message=hi",
                headers={"X-BU-ID": "BU_RL"},
            ) as resp:
                return [line async for line in resp.aiter_lines()]

        await send()
        await send()
        third = await send()

    rate_limit.reset()
    assert any("RATE_LIMITED" in line for line in third)
    assert any("retry_after_ms" in line for line in third)


async def test_chat_endpoint_emits_ping_constant():
    from ai_engine.api import sse_events

    assert sse_events.PING_INTERVAL_SECONDS == 30


async def test_chat_endpoint_guest_fallback_no_bu_header(seeded_db):
    """无身份调 /chat → 降级游客，不再 401。"""
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/chat?conversation_id=1&message=hi")
    assert resp.status_code != 401


async def test_chat_cancel_stream(seeded_db):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init = await client.post(
            "/api/v1/conversations", json={}, headers={"X-BU-ID": "BU00243780"}
        )
        conv_id = init.json()["conversation_id"]
        resp = await client.delete(
            f"/api/v1/chat/{conv_id}/stream", headers={"X-BU-ID": "BU00243780"}
        )
    assert resp.status_code == 204
