"""E2E 剧本 #9：限流全链路（默认 30/min，配置可改）。

剧本梗概：
    1. 把 chat_rate_limit_per_min 调低到 3，方便快速触发。
    2. 用同一 C 端身份连发 4 条 → 第 4 条收到 SSE error 帧 code=RATE_LIMITED，
       stop_reason=rate_limited；主 LLM 不被调。
    3. 切换到 B 端身份 → 限流 key 不同，不影响。
    4. 游客（X-Guest-ID）按 IP key（"g:ip:host"）隔离：换 IP 头不触发同窗口阈值。

异常分支：
    - 限流命中时 retry_after_ms 字段必须 > 0。
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_engine.config import settings
from ai_engine.main import app

from .conftest import (
    BU_ID,
    TOKEN_A,
    bu_headers,
    c_headers,
    event_data,
    parse_sse,
    stub_run_turn,
)


@pytest_asyncio.fixture
def tight_limit(monkeypatch):
    """把 chat_rate_limit_per_min 拉到 3，便于快速触发 429。"""
    monkeypatch.setattr(settings, "chat_rate_limit_per_min", 3, raising=False)


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


class TestRateLimit:
    async def test_burst_triggers_429_on_fourth_call(
        self, c_client: AsyncClient, conv_id: int, tight_limit, monkeypatch
    ) -> None:
        ai_called = {"n": 0}

        def _stub(**kw):
            ai_called["n"] += 1
            return [{"type": "text", "text": "ok"}]

        stub_run_turn(monkeypatch, _stub)

        # 前 3 次 200 + 正常 SSE
        for i in range(3):
            r = await c_client.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": f"q{i}"},
            )
            assert r.status_code == 200
            frames = await parse_sse(r)
            stops = event_data(frames, "message_stop")
            assert any(s.get("stop_reason") == "end_turn" for s in stops)

        # 第 4 次：限流
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "q4"}
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        errors = event_data(frames, "error")
        assert any(e.get("code") == "RATE_LIMITED" for e in errors)
        assert any(int(e.get("retry_after_ms", 0)) > 0 for e in errors)
        stops = event_data(frames, "message_stop")
        assert any(s.get("stop_reason") == "rate_limited" for s in stops)
        assert ai_called["n"] == 3, "第 4 次不应进 LLM"

    async def test_different_subject_not_affected(
        self, db_ready, tight_limit, monkeypatch
    ) -> None:
        """C 端 A 用满 → C 端 A 自己被限；B 端不受影响。"""
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])
        # C 端 A 用满 3 次
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=c_headers(TOKEN_A)
        ) as ca:
            r = await ca.post("/api/v1/conversations", json={})
            cid_a = int(r.json()["conversation_id"])
            for i in range(3):
                r = await ca.get(
                    "/api/v1/chat", params={"conversation_id": cid_a, "message": f"q{i}"}
                )
                assert r.status_code == 200
            # 第 4 次：A 被限
            r = await ca.get(
                "/api/v1/chat", params={"conversation_id": cid_a, "message": "q4"}
            )
            assert any(
                e.get("code") == "RATE_LIMITED" for e in event_data(await parse_sse(r), "error")
            )

        # B 端开新会话 + 发消息：不受 A 的窗口影响
        async with AsyncClient(
            transport=transport, base_url="http://test", headers=bu_headers(BU_ID)
        ) as cb:
            r = await cb.post("/api/v1/conversations", json={})
            cid_b = int(r.json()["conversation_id"])
            r = await cb.get(
                "/api/v1/chat", params={"conversation_id": cid_b, "message": "b1"}
            )
            assert r.status_code == 200
            frames = await parse_sse(r)
            # 没有限流错误
            assert not [e for e in event_data(frames, "error") if e.get("code") == "RATE_LIMITED"]
