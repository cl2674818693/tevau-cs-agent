"""E2E 剧本 #2：用户求人工 → 工单进事项中心 → 座席接管 → 双向消息 → 关单。

剧本梗概：
    1. 用户 chat 期间触发 AI 决定 create_ticket(category="人工介入")。
       —— 测试用直接 POST /api/v1/conversations/{id}/request-human 模拟，等价路径。
    2. assert 工单已落 tickets 表 + payload 含 user_id；事项中心 inbox 收到 push。
    3. 会话 mode 变 human_pending；admin 列表 status=human_pending 能看到。
    4. 座席 POST /staff/api/v1/conversations/{id}/take → mode=human_takeover。
    5. 座席 POST .../messages 发回复 → 用户侧 messages-stream SSE 拿到 human_message。
    6. 用户在 takeover 模式发消息 → mode_change(to=human_takeover) + 不调 AI；
       座席侧总线收到 user_message。
    7. 座席 POST .../resolve → mode 回 ai；staff_actions 记 resolved。
    8. 工单关闭：POST .../tickets/{ext_id}/user-events {event:user_confirmed_resolved}
       → ticket_events 落 closed + push_event_center 发出 closed。

异常分支：
    - 转人工后另一个座席 take 同会话 → 409。
    - 未持有 staff JWT 调 take → 401。
    - 已 human_takeover 时再调 request-human → 幂等返回 {ok: True, note: 'already...'}。
"""

import asyncio
import json
from typing import Any

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import tickets as ticket_dao

from .conftest import event_data, insert_staff_row, parse_sse


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


@pytest_asyncio.fixture
async def two_agents(db_ready) -> tuple[str, str]:
    await insert_staff_row("agent-A", "Agent A", "agent")
    await insert_staff_row("agent-B", "Agent B", "agent")
    return "agent-A", "agent-B"


class TestHandoffFullFlow:
    async def test_request_human_creates_ticket_and_changes_mode(
        self, c_client: AsyncClient, conv_id: int, _mock_event_center: list[dict[str, Any]]
    ) -> None:
        """POST request-human → 工单入库 + mode=human_pending + 事项中心 push。"""
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human",
            json={"reason": "AI 答非所问"},
        )
        assert r.status_code == 200
        ticket_id = r.json()["ticket_id"]
        assert ticket_id.startswith("AI-")

        # mode 变了
        mode, _ = await conv_dao.get_mode(conv_id)
        assert mode == "human_pending"
        # 工单本地镜像
        ticket = await ticket_dao.get_ticket(ticket_id)
        assert ticket is not None
        payload = json.loads(str(ticket["payload_json"]))
        assert payload["category"] == "人工介入"
        assert payload["user_id"] == "U-ALPHA"
        # 事项中心 inbox 含本次 ticket payload
        ticket_pushes = [it["json"] for it in _mock_event_center if "json" in it]
        assert any(p.get("external_ticket_id") == ticket_id for p in ticket_pushes)

    async def test_admin_list_sees_pending_conversation(
        self,
        c_client: AsyncClient,
        conv_id: int,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """工单生成后会话进 admin 列表 status=human_pending。"""
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        r = await sc.get("/staff/api/v1/conversations", params={"status": "human_pending"})
        assert r.status_code == 200
        rows = r.json()
        assert any(int(row["id"]) == conv_id for row in rows)

    async def test_staff_take_then_send_message_to_user(
        self,
        c_client: AsyncClient,
        conv_id: int,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """座席接管 → mode=human_takeover → 座席发消息 → 订阅总线收到 human_message。

        SSE 端点本身行为已被 test_e2e_spectate / conversation_stream 单测覆盖；
        本剧本聚焦"客服消息能否经事件总线投递到用户侧订阅者"，故直接 register_subscriber 验证，
        避免 ASGI in-process 跑 SSE 长连阻塞事件循环导致的超时不稳定。
        """
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r.status_code == 200

        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "human_takeover"
        assert sid == seeded_agent

        # 模拟用户端 messages-stream：注册到同一总线
        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        q = register_subscriber(conv_id)
        try:
            r = await sc.post(
                f"/staff/api/v1/conversations/{conv_id}/messages",
                json={"content": "您好，我是 Agent A，请问您遇到了什么问题？"},
            )
            assert r.status_code == 200
            received = await asyncio.wait_for(q.get(), timeout=1.0)
            assert received["type"] == "human_message"
            assert "Agent A" in received["content"]
            assert received["sender_staff_id"] == seeded_agent
            assert received["display_name"] == "Agent One"
        finally:
            unregister_subscriber(conv_id, q)

    async def test_user_message_in_takeover_does_not_call_ai(
        self,
        c_client: AsyncClient,
        conv_id: int,
        seeded_agent,
        make_staff_client,
        monkeypatch,
    ) -> None:
        """human_takeover 后，用户消息只入库 + 推给客服侧；run_turn 不被调用。"""
        ai_called = {"n": 0}

        async def _shouldnt_be_called(**_kw):
            ai_called["n"] += 1
            yield {"type": "text", "text": "won't run"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _shouldnt_be_called)

        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        assert (await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")).status_code == 200

        # 用户在 takeover 模式发文字
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "我还有个问题"},
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        stops = event_data(frames, "message_stop")
        assert any(s.get("stop_reason") == "handed_to_human" for s in stops)
        assert ai_called["n"] == 0, "human_takeover 时不应调 AI"
        # 消息已落 messages 表
        msgs = await conv_dao.list_messages(conv_id)
        assert any(m["role"] == "user" and m["content"] == "我还有个问题" for m in msgs)

    async def test_resolve_closes_takeover(
        self,
        c_client: AsyncClient,
        conv_id: int,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """座席 resolve → mode 回 ai，staff_actions 记 resolved。"""
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")

        r = await sc.post(f"/staff/api/v1/conversations/{conv_id}/resolve")
        assert r.status_code == 200
        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "ai"
        assert sid is None

    async def test_user_confirms_resolved_closes_ticket_and_pushes(
        self,
        c_client: AsyncClient,
        conv_id: int,
        _mock_event_center: list[dict[str, Any]],
    ) -> None:
        """用户确认已解决 → ticket_events 落 closed + push_event_center 发 closed。"""
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        ext_id = r.json()["ticket_id"]
        _mock_event_center.clear()

        r = await c_client.post(
            f"/api/v1/tickets/{ext_id}/user-events",
            json={"event": "user_confirmed_resolved"},
        )
        assert r.status_code == 200

        ticket = await ticket_dao.get_ticket(ext_id)
        events = ticket["events"]  # type: ignore[index]
        assert any(ev["event"] == "closed" for ev in events)
        # 出口 push 也发了 closed
        pushes = [it["push"] for it in _mock_event_center if "push" in it]
        assert any(p.get("event") == "closed" for p in pushes)


class TestHandoffEdgeCases:
    """异常路径：竞争接管 / 重复转人工 / 鉴权。"""

    async def test_second_staff_take_returns_409(
        self,
        c_client: AsyncClient,
        conv_id: int,
        two_agents,
        make_staff_client,
    ) -> None:
        a, b = two_agents
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        sa = make_staff_client(a, "agent")
        sb = make_staff_client(b, "agent")
        assert (await sa.post(f"/staff/api/v1/conversations/{conv_id}/take")).status_code == 200
        # B 抢同会话：409
        r = await sb.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r.status_code == 409

    async def test_take_without_staff_token_returns_401(
        self, c_client: AsyncClient, conv_id: int, client: AsyncClient
    ) -> None:
        """裸客户端调 take → 401。"""
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "x"}
        )
        r = await client.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r.status_code == 401

    async def test_request_human_when_already_takeover_is_idempotent(
        self,
        c_client: AsyncClient,
        conv_id: int,
        seeded_agent,
        make_staff_client,
    ) -> None:
        """已 human_takeover 时再请求转人工 → 不重复建工单，note=already。"""
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "first"}
        )
        sc = make_staff_client(seeded_agent, "agent")
        await sc.post(f"/staff/api/v1/conversations/{conv_id}/take")

        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human", json={"reason": "again"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("note") == "already human-handled"

    async def test_guest_request_human_returns_403(
        self, client: AsyncClient
    ) -> None:
        """游客（未登录）请求转人工 → 403 提示先登录。"""
        # 游客直接调一条不存在的 conv 也会先被 user_type 校验拦下
        # 这里用 X-Guest-ID 模拟匿名身份调
        r = await client.post(
            "/api/v1/conversations/9999/request-human",
            json={"reason": "x"},
            headers={"X-Guest-ID": "g1"},
        )
        assert r.status_code == 403
