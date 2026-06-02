"""C 端通用 SSE 流：/api/v1/conversations/{cid}/messages-stream。

该端点是 while True 的常驻流：httpx + ASGITransport 不能正常 iter 出帧（一直 buffer），
因此正向用例直接验 USER_FACING_EVENTS 集合行为 + 订阅/取消订阅机制；
HTTP 层只验鉴权（HTTPException 在生成器前抛出，能正常返回 403）。

被测：
- register_subscriber / unregister_subscriber：会话维度按 conv_id 多订阅者
- USER_FACING_EVENTS：仅 5 种事件会下发给用户侧；其他被过滤
- 归属校验：跨用户 / 未登录 → 403（HTTP 层）
"""

import asyncio

import pytest
from httpx import AsyncClient

from ai_engine.api import conversation_stream as _cs_mod
from ai_engine.api import staff_conversations as _sc

from .conftest import TOKEN_B, auth_headers


# ────────── 内部行为：直接走订阅总线 ──────────


class TestUserFacingEventsFilter:
    """USER_FACING_EVENTS 是个白名单：5 种事件可下发，其他类型应被过滤。"""

    def test_human_message_included(self) -> None:
        assert "human_message" in _cs_mod.USER_FACING_EVENTS

    def test_assistant_message_included(self) -> None:
        assert "assistant_message" in _cs_mod.USER_FACING_EVENTS

    def test_mode_change_included(self) -> None:
        assert "mode_change" in _cs_mod.USER_FACING_EVENTS

    def test_transferred_included(self) -> None:
        assert "transferred" in _cs_mod.USER_FACING_EVENTS

    def test_request_human_included(self) -> None:
        assert "request_human" in _cs_mod.USER_FACING_EVENTS

    def test_user_message_excluded(self) -> None:
        """user_message 是用户 → 客服方向，不应出现在用户侧常驻流。"""
        assert "user_message" not in _cs_mod.USER_FACING_EVENTS

    def test_ai_draft_ready_excluded(self) -> None:
        """ai_draft_ready 是客服侧 review 信号，用户不可见。"""
        assert "ai_draft_ready" not in _cs_mod.USER_FACING_EVENTS

    def test_assistant_text_spectator_excluded(self) -> None:
        """assistant_text 是旁观帧（客服旁观 AI 流文本），不下发给用户。"""
        assert "assistant_text" not in _cs_mod.USER_FACING_EVENTS


# ────────── 订阅总线：register / publish / unregister ──────────


class TestSubscriberBus:
    async def test_register_returns_async_queue(self) -> None:
        q = _sc.register_subscriber(12345)
        assert isinstance(q, asyncio.Queue)
        _sc.unregister_subscriber(12345, q)

    async def test_publish_reaches_local_subscriber(self) -> None:
        q = _sc.register_subscriber(99001)
        try:
            _sc._publish(99001, {"type": "mode_change", "to": "ai"})
            ev = await asyncio.wait_for(q.get(), timeout=1.0)
            assert ev["type"] == "mode_change"
        finally:
            _sc.unregister_subscriber(99001, q)

    async def test_multiple_subscribers_all_receive(self) -> None:
        q1 = _sc.register_subscriber(99002)
        q2 = _sc.register_subscriber(99002)
        try:
            _sc._publish(99002, {"type": "human_message", "content": "hi"})
            e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
            e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
            assert e1 == e2 == {"type": "human_message", "content": "hi"}
        finally:
            _sc.unregister_subscriber(99002, q1)
            _sc.unregister_subscriber(99002, q2)

    async def test_publish_isolated_per_conv(self) -> None:
        qa = _sc.register_subscriber(99003)
        qb = _sc.register_subscriber(99004)
        try:
            _sc._publish(99003, {"type": "mode_change", "to": "ai"})
            # b 不应收到 a 的事件
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(qb.get(), timeout=0.2)
            assert (await qa.get())["type"] == "mode_change"
        finally:
            _sc.unregister_subscriber(99003, qa)
            _sc.unregister_subscriber(99004, qb)

    async def test_unregister_removes_subscriber(self) -> None:
        before = len(_sc._subscribers.get(99005, []))
        q = _sc.register_subscriber(99005)
        assert len(_sc._subscribers[99005]) == before + 1
        _sc.unregister_subscriber(99005, q)
        assert len(_sc._subscribers.get(99005, [])) == before


# ────────── HTTP 层：归属校验（HTTPException 在 generator 前抛出，可正常断言） ──────────


class TestMessagesStreamAuth:
    async def test_other_user_forbidden(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        r = await client.get(
            f"/api/v1/conversations/{conv_id}/messages-stream",
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_guest_forbidden(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        r = await client.get(f"/api/v1/conversations/{conv_id}/messages-stream")
        assert r.status_code == 403

    async def test_nonexistent_conversation_forbidden(
        self, c_client: AsyncClient
    ) -> None:
        r = await c_client.get("/api/v1/conversations/9999999/messages-stream")
        assert r.status_code == 403
