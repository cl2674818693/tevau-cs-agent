"""E2E 剧本 #1：用户首次咨询全链路。

剧本梗概：
    1. C 端 (Bearer) 调 POST /api/v1/conversations 建会话；返回 conv_id + greeting + mode=ai。
    2. 用户连续发 3 条消息（SSE chat）。每条都被 fake_stream 回应一段 text，并落库。
    3. 用户对最后一条 AI 回复点 👍；feedback DAO 写入 up 一票。
    4. 用户主动用第二条消息的 client_message_id 重发：应命中幂等重放，不再走 LLM。
    5. 读 /api/v1/conversations/{id}/messages 拉历史，断言 6 条 user/assistant 消息次序正确。

异常分支：
    - 用同一 Bearer 但伪造他人的 conversation_id → 403（IDOR 防护）。
    - 未登录裸调 chat 端点 → 没有 conversation_id 归属 → 403。
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.main import app
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import feedback as fb_dao

from .conftest import (
    TOKEN_B,
    c_headers,
    event_data,
    parse_sse,
    stub_run_turn,
)

# 让 fake_stream 永远回固定一段（每次 chat 都用同一份）。
_GREET_EVENTS = [{"type": "text", "text": "好的，我帮您看看。"}]


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_type"] == "c"
    assert body["mode"] == "ai"
    assert body.get("greeting")
    return int(body["conversation_id"])


class TestChatFullFlow:
    async def test_init_conversation_returns_meta(self, c_client: AsyncClient) -> None:
        """初始化会话返回 conv_id + greeting + mode=ai；不该带 staff_name。"""
        r = await c_client.post("/api/v1/conversations", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "ai"
        assert body["staff_name"] is None
        assert body["display_name"] == body["display_name"]  # 至少存在
        assert body["limits"]["max_turns"] == 20

    async def test_three_turn_chat_and_history_replay(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """3 轮 chat → history 端点能拉到全部 user/assistant 对。"""
        stub_run_turn(monkeypatch, _GREET_EVENTS)
        questions = ["余额还有多少？", "我的卡为什么锁了？", "怎么解锁？"]
        for i, q in enumerate(questions):
            r = await c_client.get(
                "/api/v1/chat",
                params={
                    "conversation_id": conv_id,
                    "message": q,
                    "client_message_id": f"cmid-{i}",
                },
            )
            assert r.status_code == 200
            frames = await parse_sse(r)
            # 必有 conversation/message_start/content_block_delta/message_stop 四类
            event_names = {f.get("event") for f in frames}
            assert "conversation" in event_names
            assert "message_start" in event_names
            assert "content_block_delta" in event_names
            assert "message_stop" in event_names
            deltas = event_data(frames, "content_block_delta")
            assert any("好的" in d["delta"]["text"] for d in deltas)

        # history 拉回放
        r = await c_client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert r.status_code == 200
        msgs = r.json()["messages"]
        # 3 user + 3 assistant；顺序：user/assistant 交替
        roles = [m["role"] for m in msgs]
        assert roles.count("user") == 3
        assert roles.count("assistant") == 3
        for i in range(0, 6, 2):
            assert msgs[i]["role"] == "user"
            assert msgs[i + 1]["role"] == "assistant"

    async def test_thumbs_up_feedback_writes_row(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """对某条 AI 回复点 👍 → message_feedback 表落 up 一票，不触发 needs_review。"""
        stub_run_turn(monkeypatch, _GREET_EVENTS)
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "查余额", "client_message_id": "f1"},
        )
        assert r.status_code == 200
        # 取该会话最新一条 assistant 行的 id
        msgs = await conv_dao.list_messages(conv_id)
        assistant_ids = [m["id"] for m in msgs if m["role"] == "assistant"]
        assert assistant_ids, "expected at least one assistant message"
        latest_assistant = assistant_ids[-1]

        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": latest_assistant, "rating": "up"},
        )
        assert r.status_code == 200
        # DAO 直接读：up 一票，down 零票；conversations.needs_review 仍 0
        rows = await fb_dao.list_feedback(conv_id)
        assert len(rows) == 1
        assert rows[0]["rating"] == "up"
        # needs_review 列只在 down 时写 1；up 不该触发
        row = await conv_dao.get_meta_with_risk(conv_id)
        assert int(row["needs_review"] or 0) == 0

    async def test_idempotent_replay_does_not_recall_llm(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """同 client_message_id 第二次发 → 不再触发 run_turn，只重放历史 assistant。"""
        call_counter = {"n": 0}

        def _factory(**kw):
            call_counter["n"] += 1
            return [{"type": "text", "text": "答案 A"}]

        stub_run_turn(monkeypatch, _factory)

        params = {
            "conversation_id": conv_id,
            "message": "原始问题",
            "client_message_id": "dup-1",
        }
        r1 = await c_client.get("/api/v1/chat", params=params)
        assert r1.status_code == 200
        assert call_counter["n"] == 1

        # 第二次：相同 cmid → 重放路径，不再进 LLM
        r2 = await c_client.get("/api/v1/chat", params=params)
        assert r2.status_code == 200
        assert call_counter["n"] == 1, "duplicate client_message_id 应触发幂等重放"
        # 重放帧里也应有 message_start/message_stop（虽 stop_reason=replayed）
        frames = await parse_sse(r2)
        stop_frames = event_data(frames, "message_stop")
        assert any(s.get("stop_reason") == "replayed" for s in stop_frames)

    async def test_idor_cross_user_conversation_returns_403(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """A 用户的 conversation_id，B 用户用自己的 Bearer 调 → 必须 403。"""
        stub_run_turn(monkeypatch, _GREET_EVENTS)
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=c_headers(TOKEN_B)
        ) as c_b:
            r = await c_b.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "偷看"},
            )
            assert r.status_code == 403

    async def test_unauthenticated_chat_to_owned_conv_returns_403(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        """未携带任何身份头（游客）调他人 conv → 403 not your conversation。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as anon:
            r = await anon.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "?"},
            )
            assert r.status_code == 403

    async def test_resume_existing_conversation(self, c_client: AsyncClient) -> None:
        """init 时带 resume=旧 conv_id → 续接历史，不新建。"""
        r1 = await c_client.post("/api/v1/conversations", json={})
        cid = int(r1.json()["conversation_id"])

        r2 = await c_client.post("/api/v1/conversations", json={"resume": cid})
        assert r2.status_code == 200
        assert int(r2.json()["conversation_id"]) == cid

    async def test_resume_other_users_conv_falls_back_to_new(
        self, c_client: AsyncClient
    ) -> None:
        """伪造 resume=别人会话 id → 安全降级为新建（不应原路返回敌方 id）。"""
        # 先建一条 B 的会话
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=c_headers(TOKEN_B)
        ) as c_b:
            r = await c_b.post("/api/v1/conversations", json={})
            other_id = int(r.json()["conversation_id"])

        # A 试图 resume 它
        r2 = await c_client.post("/api/v1/conversations", json={"resume": other_id})
        new_id = int(r2.json()["conversation_id"])
        assert new_id != other_id
