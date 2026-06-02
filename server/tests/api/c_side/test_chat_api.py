"""C 端 chat 主端点测试：/api/v1/chat (SSE) + /api/v1/chat/{conv}/stream (cancel)。

mock 策略：
- runtime.run_turn 被替换成固定事件序列（不打 anthropic）
- 不涉及 budget 拒服（默认 token 用量为 0）

SSE 解析用 conftest.parse_sse —— 把 EventSourceResponse 拆成 {event, data} 帧。
注意：httpx ASGITransport 会把整个流读完再返回 .text；这里测试事件无穷流不适用，
所以 mock 的 run_turn 必须是有限序列（流自然结束，message_stop 收尾）。
"""

import json

from httpx import AsyncClient

from ai_engine.governance import token_budget as _tb

from .conftest import TOKEN_B, auth_headers, parse_sse, stub_run_turn


class TestChatHappyPath:
    """正常 AI 回合：conversation → message_start → content_block_delta* → message_stop。"""

    async def test_streams_text_deltas(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(monkeypatch, [{"type": "text", "text": "Hello world"}])
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "hi"},
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        names = [f["event"] for f in frames]
        # 首事件 conversation；尾事件 message_stop
        assert names[0] == "conversation"
        assert names[-1] == "message_stop"
        assert "message_start" in names
        # text_delta 帧内容拼起来等于 stub 文本
        text_blob = "".join(
            json.loads(f["data"])["delta"]["text"]
            for f in frames
            if f["event"] == "content_block_delta"
        )
        assert text_blob == "Hello world"

    async def test_first_event_carries_conversation_meta(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        frames = await parse_sse(r)
        head = json.loads(frames[0]["data"])
        assert head["conversation_id"] == conv_id
        assert head["user_type"] == "c"
        assert "model" in head

    async def test_message_stop_has_end_turn_reason(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(monkeypatch, [{"type": "text", "text": "x"}])
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        frames = await parse_sse(r)
        last = json.loads(frames[-1]["data"])
        assert last["stop_reason"] == "end_turn"

    async def test_tool_use_and_tool_result_events_emitted(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(
            monkeypatch,
            [
                {"type": "tool_call", "id": "tu_1", "name": "query_user", "input": {}},
                {"type": "tool_result", "id": "tu_1", "name": "query_user", "ok": True},
                {"type": "text", "text": "已查到"},
            ],
        )
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "查我的资料"}
        )
        names = [f["event"] for f in await parse_sse(r)]
        assert "tool_use" in names
        assert "tool_result" in names

    async def test_tool_result_failure_marked_is_error(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(
            monkeypatch,
            [
                {"type": "tool_result", "id": "tu_x", "name": "query_x", "ok": False},
                {"type": "text", "text": "fail-soft"},
            ],
        )
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "x"}
        )
        frames = await parse_sse(r)
        tr = next(f for f in frames if f["event"] == "tool_result")
        assert json.loads(tr["data"])["is_error"] is True

    async def test_system_event_mapped_to_warning(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(
            monkeypatch,
            [
                {"type": "system", "text": "您今日额度已用 80%"},
                {"type": "text", "text": "好的"},
            ],
        )
        frames = await parse_sse(
            await c_client.get(
                "/api/v1/chat", params={"conversation_id": conv_id, "message": "x"}
            )
        )
        assert any(f["event"] == "warning" for f in frames)

    async def test_runtime_error_event_mapped_to_error(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        stub_run_turn(
            monkeypatch,
            [{"type": "error", "code": "INTERNAL_ERROR", "text": "boom"}],
        )
        frames = await parse_sse(
            await c_client.get(
                "/api/v1/chat", params={"conversation_id": conv_id, "message": "x"}
            )
        )
        err = next(f for f in frames if f["event"] == "error")
        assert json.loads(err["data"])["code"] == "INTERNAL_ERROR"


class TestChatAuth:
    """归属校验：身份缺失 / 跨用户 / 不存在的会话 都应 403（端点未区分 401/404，统一 403）。"""

    async def test_guest_cannot_chat_to_c_conversation(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        # 不带 token → guest 身份；user_type != 'c' → 归属失败
        r = await client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        assert r.status_code == 403

    async def test_other_user_cannot_chat(
        self, client: AsyncClient, conv_id: int
    ) -> None:
        r = await client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "hi"},
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_nonexistent_conversation_returns_403(
        self, c_client: AsyncClient
    ) -> None:
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": 99999999, "message": "x"}
        )
        assert r.status_code == 403


class TestChatValidation:
    """参数校验：必填缺失 → 422；类型错 → 422。"""

    async def test_missing_message_returns_422(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        r = await c_client.get("/api/v1/chat", params={"conversation_id": conv_id})
        assert r.status_code == 422

    async def test_missing_conversation_id_returns_422(
        self, c_client: AsyncClient
    ) -> None:
        r = await c_client.get("/api/v1/chat", params={"message": "x"})
        assert r.status_code == 422

    async def test_conversation_id_must_be_int(
        self, c_client: AsyncClient
    ) -> None:
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": "not-int", "message": "x"}
        )
        assert r.status_code == 422


class TestChatRateLimit:
    """spec §6.4 兜底层：单 subject 每分钟超阈值 → SSE error(RATE_LIMITED) + message_stop。"""

    async def test_rate_limited_after_threshold(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        # 把 limit 调到 1：第一发应 OK，第二发应被限流
        monkeypatch.setattr(
            "ai_engine.governance.rate_limit.settings.chat_rate_limit_per_min", 1
        )
        stub_run_turn(monkeypatch, [{"type": "text", "text": "y"}])
        ok = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "1"}
        )
        assert ok.status_code == 200
        ko = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "2"}
        )
        frames = await parse_sse(ko)
        err = next(f for f in frames if f["event"] == "error")
        body = json.loads(err["data"])
        assert body["code"] == "RATE_LIMITED"
        assert body["retry_after_ms"] > 0
        stop = json.loads(frames[-1]["data"])
        assert stop["stop_reason"] == "rate_limited"


class TestChatBudgetExhausted:
    """spec §8 当日 token 上限：硬闸 → warning + message_stop(budget_exceeded)，不进 agent loop。"""

    async def test_exhausted_short_circuits(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        monkeypatch.setattr(_tb, "is_exhausted", lambda *a, **k: _fake_true())
        called = []
        stub_run_turn(monkeypatch, [{"type": "text", "text": "should-not-stream"}])
        # 顺便 stub 一下 run_turn 让 stub 列表注册成功
        from ai_engine.agent import runtime
        orig = runtime.run_turn

        async def _wrap(**kw):
            called.append(1)
            async for ev in orig(**kw):
                yield ev

        monkeypatch.setattr(runtime, "run_turn", _wrap)
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "x"}
        )
        frames = await parse_sse(r)
        assert any(f["event"] == "warning" for f in frames)
        stop = json.loads(frames[-1]["data"])
        assert stop["stop_reason"] == "budget_exceeded"
        assert called == []  # 没进 agent loop


async def _fake_true() -> bool:
    return True


class TestChatPersistence:
    """副作用断言：run_turn 被以正确参数调用；cancel 端点 204；不影响业务库。"""

    async def test_run_turn_invoked_with_user_message(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """断言 chat 端点把 user_message / conversation_id / 身份正确透传给 runtime.run_turn。"""
        captured: dict[str, object] = {}

        async def _capture(**kwargs):
            captured.update(kwargs)
            yield {"type": "text", "text": "ok"}

        from ai_engine.agent import runtime
        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _capture)
        monkeypatch.setattr(runtime, "run_turn", _capture)

        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "hello",
                "client_message_id": "client-1",
            },
        )
        assert r.status_code == 200
        # 等 stream 完整消费
        await parse_sse(r)
        assert captured["conversation_id"] == conv_id
        assert captured["user_message"] == "hello"
        assert captured["client_message_id"] == "client-1"
        assert captured["user_type"] == "c"

    async def test_cancellation_endpoint_requires_ownership(
        self, c_client: AsyncClient, client: AsyncClient, conv_id: int
    ) -> None:
        # 不带身份 → 403
        r = await client.delete(f"/api/v1/chat/{conv_id}/stream")
        assert r.status_code == 403
        # 带身份 + 无活跃流 → 204（端点行为：信号 set 即可，不存在也不抛）
        ok = await c_client.delete(f"/api/v1/chat/{conv_id}/stream")
        assert ok.status_code == 204
