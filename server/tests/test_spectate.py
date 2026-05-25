import asyncio
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def staff_tokens(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("SR1", "高级", "senior", "x")
    return {
        "agent": issue_staff_token("AG1", "agent"),
        "senior": issue_staff_token("SR1", "senior"),
    }


async def test_agent_cannot_spectate(staff_tokens):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            f"/staff/api/v1/conversations/{cid}/spectate-stream",
            headers={"Authorization": f"Bearer {staff_tokens['agent']}"},
        )
    assert r.status_code == 403


async def test_chat_publishes_spectator_events(seeded_db, monkeypatch, fake_stream):
    """AI 模式下 chat 把 user_message / assistant_text 推到旁观总线。"""
    from ai_engine.api import chat as chat_mod
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")

    captured: list[dict] = []
    monkeypatch.setattr(
        chat_mod, "publish_conversation_event", lambda _cid, ev: captured.append(ev)
    )

    fake = MagicMock()
    fake.messages.stream = fake_stream(
        MagicMock(
            content=[MagicMock(type="text", text="AI 正在处理")],
            stop_reason="end_turn",
            usage=MagicMock(input_tokens=1, output_tokens=1),
        )
    )
    monkeypatch.setattr(ac, "_client", fake)

    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={cid}&message=hi",
            headers={"X-BU-ID": "BU00243780"},
        ) as cr:
            async for _ in cr.aiter_lines():
                pass

    kinds = [e["type"] for e in captured]
    assert "user_message" in kinds
    assert "assistant_text" in kinds
    assert any(e.get("content") == "AI 正在处理" for e in captured)


async def test_bus_delivers_only_when_subscribed():
    """publish_conversation_event 仅在有订阅者时投递（旁观接入后才产生开销）。"""
    from ai_engine.api import staff_conversations as sc

    cid = 99123
    # 无订阅者：不抛错、不投递
    sc.publish_conversation_event(cid, {"type": "assistant_text", "content": "x"})

    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=10)
    sc._subscribers[cid].append(q)
    try:
        sc.publish_conversation_event(cid, {"type": "assistant_text", "content": "hi"})
        ev = await asyncio.wait_for(q.get(), timeout=1)
        assert ev["content"] == "hi"
    finally:
        sc._subscribers[cid].remove(q)
