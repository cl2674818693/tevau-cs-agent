import asyncio

from httpx import ASGITransport, AsyncClient


async def test_messages_stream_rejects_cross_subject(seeded_db):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU1")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            f"/api/v1/conversations/{cid}/messages-stream",
            headers={"X-BU-ID": "BU_OTHER"},
        )
    assert r.status_code == 403


async def test_user_facing_events_filter():
    from ai_engine.api.conversation_stream import USER_FACING_EVENTS

    # 客服→用户方向的事件转发
    assert "human_message" in USER_FACING_EVENTS
    assert "assistant_message" in USER_FACING_EVENTS
    assert "mode_change" in USER_FACING_EVENTS
    # 用户自己发的 / 给客服侧的 / 旁观事件不回灌用户
    assert "user_message" not in USER_FACING_EVENTS
    assert "ai_draft_ready" not in USER_FACING_EVENTS
    assert "assistant_text" not in USER_FACING_EVENTS


async def test_bus_delivers_human_message_to_user_subscriber(seeded_db):
    """客服 send_message → publish human_message → 用户侧订阅者收到。"""
    from ai_engine.api import staff_conversations as sc
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU1")
    q = sc.register_subscriber(cid)
    try:
        sc._publish(
            cid, {"type": "human_message", "content": "您好，已为您解锁", "sender_staff_id": "S1"}
        )
        ev = await asyncio.wait_for(q.get(), timeout=1)
        assert ev["type"] == "human_message" and "解锁" in ev["content"]
    finally:
        sc.unregister_subscriber(cid, q)
