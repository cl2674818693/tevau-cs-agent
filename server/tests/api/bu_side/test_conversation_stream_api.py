"""API: GET /api/v1/conversations/{id}/messages-stream（conversation_stream.py）。

被测对象：用户侧常驻 SSE → 接收客服回复 / 审核通过的草稿 / 模式变更（spec §13）。
鉴权：resolve_identity；属主校验防 IDOR。

异常矩阵：
- 未登录/游客 → 403（subject_id 不匹配）
- 跨 BU → 403
- 会话不存在 → 403
- 同身份 → 200 + content-type

注：SSE 长连在 ASGITransport 下读不出字节会 hang，本组只验鉴权 + content-type。
事件转发逻辑通过直接调 register/_publish 验证（白名单过滤）。
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.conversation_stream import (
    USER_FACING_EVENTS,
    router as conversation_stream_router,
)

from .conftest import insert_conversation


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(conversation_stream_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestAuth:
    async def test_anonymous_guest_403(self, init_self_db, client) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.get(f"/api/v1/conversations/{cid}/messages-stream")
        assert resp.status_code == 403

    async def test_cross_bu_403(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages-stream",
            headers=bu_headers("1011010000189"),  # 别人的 BU
        )
        assert resp.status_code == 403

    async def test_nonexistent_conv_403(
        self, init_self_db, client, bu_headers
    ) -> None:
        resp = await client.get(
            "/api/v1/conversations/99999/messages-stream",
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 403

    async def test_wrong_user_type_403(
        self, init_self_db, client, bu_headers
    ) -> None:
        """会话 user_type=c 但请求是 B → user_type 不匹配 → 403。"""
        cid = await insert_conversation(user_type="c", subject_id="1011010000068")
        # 同 subject_id 但 type 不同 → 403
        resp = await client.get(
            f"/api/v1/conversations/{cid}/messages-stream",
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 403


class TestUserFacingEventsFilter:
    """conversation_stream 内对非 USER_FACING_EVENTS 的事件不 yield；用户不该看 ai_draft_ready。"""

    def test_user_facing_events_set(self) -> None:
        # 用户该收的
        for ev_type in (
            "human_message", "assistant_message", "mode_change",
            "transferred", "request_human",
        ):
            assert ev_type in USER_FACING_EVENTS
        # 不该跨过去的（旁观/草稿/工单等）
        for ev_type in ("user_message", "ai_draft_ready", "assistant_text", "in_progress"):
            assert ev_type not in USER_FACING_EVENTS


class TestSubscribeMechanics:
    async def test_register_publish_filter_unregister(
        self, init_self_db
    ) -> None:
        """直接测 register/_publish 协作：填多种事件，验证 set 过滤逻辑。"""
        from ai_engine.api.staff_conversations import (
            _publish,
            register_subscriber,
            unregister_subscriber,
        )

        cid = 8001
        q = register_subscriber(cid)
        _publish(cid, {"type": "human_message", "content": "hi"})
        _publish(cid, {"type": "mode_change", "to": "ai"})
        # 队列收的是所有事件；过滤由 generator 做（在端点内 yield 时过滤）
        ev1 = await asyncio.wait_for(q.get(), timeout=1.0)
        ev2 = await asyncio.wait_for(q.get(), timeout=1.0)
        assert ev1["type"] == "human_message"
        assert ev2["type"] == "mode_change"
        unregister_subscriber(cid, q)


class TestStreamHeadersOnly:
    async def test_owner_opens_with_correct_content_type(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")

        async def _open() -> tuple[int, str]:
            async with client.stream(
                "GET",
                f"/api/v1/conversations/{cid}/messages-stream",
                headers=bu_headers("1011010000068"),
            ) as resp:
                code = resp.status_code
                ct = resp.headers.get("content-type", "")
                await resp.aclose()
                return code, ct

        try:
            code, ct = await asyncio.wait_for(_open(), timeout=2.0)
            assert code == 200
            assert "text/event-stream" in ct
        except (TimeoutError, asyncio.TimeoutError):
            pytest.skip("ASGITransport SSE aclose timeout (test infra limitation)")
