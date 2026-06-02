"""E2E 剧本 #3：座席接管后 AI 草稿 → 客服 review → approve/reject → 用户收到。

剧本梗概：
    1. 用户 chat → 求人工 → mode=human_pending；座席 take → human_takeover。
    2. 座席 POST .../ai-draft/enable → mode=ai_draft；分派给本座席。
    3. 用户继续发消息：chat 走 collect_full_response → 不流给用户；
       落 ai_draft 行 + 推 ai_draft_ready 到客服总线。
    4. 座席从 DAO 看到草稿；POST .../ai-draft/approve → 草稿作 assistant 消息发出 +
       推 assistant_message → 草稿清空。
    5. 第二轮再触发 AI 出草稿；座席 POST .../ai-draft/reject {rewrite:"…"} → 改写以
       human_agent 身份发出 + 推 human_message。
    6. 座席 POST .../ai-draft/disable → 回到 human_takeover 模式？看代码：
       disable 实际把 mode 切回 'ai' 并清 assigned_staff_id（见 source）。

异常分支：
    - 非指派座席调 approve → 403。
    - 草稿不存在时 approve / reject → 404。
"""


import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao

from .conftest import insert_staff_row, stub_run_turn

_AI_REPLY_EVENTS = [{"type": "text", "text": "您的卡片处于风控复核状态，预计 24 小时内解锁。"}]


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


@pytest_asyncio.fixture
async def takeover_session(
    c_client: AsyncClient,
    conv_id: int,
    seeded_agent,
    make_staff_client,
):
    """预置：用户已转人工 + 座席已接管。返回 (sc, conv_id, agent_id)。"""
    await c_client.post(
        f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
    )
    sc = make_staff_client(seeded_agent, "agent")
    r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")
    assert r.status_code == 200
    return sc, conv_id, seeded_agent


class TestAiDraftHappyPath:
    async def test_enable_ai_draft_then_user_message_generates_draft(
        self, c_client: AsyncClient, takeover_session, monkeypatch
    ) -> None:
        sc, conv_id, _ = takeover_session
        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        assert r.status_code == 200
        mode, _ = await conv_dao.get_mode(conv_id)
        assert mode == "ai_draft"

        # 让 collect_full_response 回固定文本
        stub_run_turn(monkeypatch, _AI_REPLY_EVENTS)

        # 用户发消息：走 ai_draft 路径，不流给用户
        from ai_engine.api.staff_conversations import register_subscriber, unregister_subscriber

        q = register_subscriber(conv_id)
        try:
            r = await c_client.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "我的卡呢？"},
            )
            assert r.status_code == 200
            # 草稿已落库
            draft = await conv_dao.get_latest_ai_draft(conv_id)
            assert draft == _AI_REPLY_EVENTS[0]["text"]
            # 客服总线收到 ai_draft_ready
            import asyncio as _aio

            got = await _aio.wait_for(q.get(), timeout=1.0)
            assert got["type"] == "ai_draft_ready"
            assert got["draft"] == _AI_REPLY_EVENTS[0]["text"]
        finally:
            unregister_subscriber(conv_id, q)

    async def test_approve_draft_publishes_assistant_message(
        self, c_client: AsyncClient, takeover_session, monkeypatch
    ) -> None:
        sc, conv_id, _ = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        stub_run_turn(monkeypatch, _AI_REPLY_EVENTS)
        await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "我的卡呢？"},
        )

        from ai_engine.api.staff_conversations import register_subscriber, unregister_subscriber

        q = register_subscriber(conv_id)
        try:
            r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/approve")
            assert r.status_code == 200
            import asyncio as _aio

            ev = await _aio.wait_for(q.get(), timeout=1.0)
            assert ev["type"] == "assistant_message"
            assert ev["content"] == _AI_REPLY_EVENTS[0]["text"]
        finally:
            unregister_subscriber(conv_id, q)
        # 草稿清空
        assert await conv_dao.get_latest_ai_draft(conv_id) is None
        # assistant 消息已写入 messages 表
        msgs = await conv_dao.list_messages(conv_id)
        assert any(
            m["role"] == "assistant" and _AI_REPLY_EVENTS[0]["text"] in str(m["content"])
            for m in msgs
        )

    async def test_reject_draft_publishes_human_rewrite(
        self, c_client: AsyncClient, takeover_session, monkeypatch
    ) -> None:
        sc, conv_id, agent_id = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        stub_run_turn(monkeypatch, _AI_REPLY_EVENTS)
        await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "ok"}
        )

        from ai_engine.api.staff_conversations import register_subscriber, unregister_subscriber

        q = register_subscriber(conv_id)
        try:
            r = await sc.post(
                f"/staff/api/v1/conversations/{conv_id}/ai-draft/reject",
                json={"rewrite": "我帮您去查一下，请稍候。"},
            )
            assert r.status_code == 200
            import asyncio as _aio

            ev = await _aio.wait_for(q.get(), timeout=1.0)
            assert ev["type"] == "human_message"
            assert ev["sender_staff_id"] == agent_id
            assert "稍候" in ev["content"]
        finally:
            unregister_subscriber(conv_id, q)
        assert await conv_dao.get_latest_ai_draft(conv_id) is None

    async def test_disable_ai_draft_returns_to_ai(
        self, c_client: AsyncClient, takeover_session
    ) -> None:
        sc, conv_id, _ = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/disable")
        assert r.status_code == 200
        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "ai"
        assert sid is None


class TestAiDraftEdgeCases:
    async def test_approve_without_pending_draft_returns_404(
        self, takeover_session
    ) -> None:
        sc, conv_id, _ = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/approve")
        assert r.status_code == 404

    async def test_reject_without_pending_draft_returns_404(
        self, takeover_session
    ) -> None:
        sc, conv_id, _ = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        r = await sc.post(
            f"/staff/api/v1/conversations/{conv_id}/ai-draft/reject",
            json={"rewrite": "anything"},
        )
        assert r.status_code == 404

    async def test_other_staff_cannot_approve(
        self,
        c_client: AsyncClient,
        takeover_session,
        make_staff_client,
        monkeypatch,
    ) -> None:
        """非指派座席尝试 approve → 403。"""
        sc, conv_id, _ = takeover_session
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/enable")
        stub_run_turn(monkeypatch, _AI_REPLY_EVENTS)
        await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        # 切到另一位座席（与 takeover_session 里 agent-1 不同）
        await insert_staff_row("agent-X", "Agent X", "agent")
        sx = make_staff_client("agent-X", "agent")
        r = await sx.post(f"/staff/api/v1/conversations/{conv_id}/ai-draft/approve")
        assert r.status_code == 403
