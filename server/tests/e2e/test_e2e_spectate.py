"""E2E 剧本 #6：旁观者订阅 AI 处理过程的总线（senior / engineer 观测 / 复盘）。

剧本梗概：
    1. 用户开会话，stub 让 run_turn 既 yield text 也 yield tool_call/tool_result/system 事件。
    2. 旁观者订阅 register_subscriber（等价 GET .../spectate-stream，但 in-process SSE 不便）。
    3. 用户 chat → 旁观总线应能拿到：user_message(text+attachments) / assistant_text /
       tool_call / tool_result / 任一系统事件。
    4. agent 角色调 spectate-stream → 403（只 senior/engineer 可见）。

异常分支：
    - 多旁观者同时订阅：每人都能完整收到事件（fan-out 而非互斥消费）。
    - 旁观期间会话 mode 变 human_pending → 旁观者仍能拿到 mode_change 事件。
"""

import asyncio
from typing import Any

import pytest_asyncio
from httpx import AsyncClient

from .conftest import insert_staff_row, stub_run_turn


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


@pytest_asyncio.fixture
async def senior(db_ready) -> str:
    await insert_staff_row("senior-1", "Senior One", "senior")
    return "senior-1"


@pytest_asyncio.fixture
async def engineer(db_ready) -> str:
    await insert_staff_row("eng-1", "Engineer One", "engineer")
    return "eng-1"


@pytest_asyncio.fixture
async def agent(db_ready) -> str:
    await insert_staff_row("agent-1", "Agent One", "agent")
    return "agent-1"


async def _drain_until(queue: asyncio.Queue, predicate, timeout_s: float = 1.0):
    """从订阅队列里 drain 事件直到 predicate(ev) 为 True，或超时抛 AssertionError。

    形参用 timeout_s 而非 timeout，避免与 asyncio.timeout/httpx.timeout 命名冲突
    （ruff ASYNC109）。
    """
    collected: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(timeout_s):
            while True:
                ev = await queue.get()
                collected.append(ev)
                if predicate(ev):
                    return collected
    except TimeoutError as e:
        raise AssertionError(f"predicate never matched; collected={collected}") from e


class TestSpectateBus:
    async def test_spectator_sees_runtime_events(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """旁观者能收到 user_message + assistant_text + tool_call + tool_result + system。"""
        events = [
            {"type": "text", "text": "我先查一下"},
            {"type": "tool_call", "id": "t1", "name": "query_balance", "input": {}},
            {"type": "tool_result", "id": "t1", "name": "query_balance", "ok": True},
            {"type": "system", "text": "您今日 AI 服务额度已用 80%。"},
            {"type": "text", "text": "您的余额是 ¥123.45"},
        ]
        stub_run_turn(monkeypatch, events)

        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        q = register_subscriber(conv_id)
        try:
            r = await c_client.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "查一下余额"},
            )
            assert r.status_code == 200
            collected = await _drain_until(
                q, lambda e: e.get("type") == "system", timeout_s=1.5
            )
            kinds = [e.get("type") for e in collected]
            # 顺序：first 一定是 user_message（chat.py 在 run_turn 之前 publish）
            assert kinds[0] == "user_message"
            # text 在旁观侧改名为 assistant_text
            assert "assistant_text" in kinds
            assert "tool_call" in kinds
            assert "tool_result" in kinds
            assert "system" in kinds
        finally:
            unregister_subscriber(conv_id, q)

    async def test_two_spectators_each_get_full_stream(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """fan-out：两个 subscriber 都应收到 user_message。"""
        stub_run_turn(monkeypatch, [{"type": "text", "text": "hi"}])
        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        q1 = register_subscriber(conv_id)
        q2 = register_subscriber(conv_id)
        try:
            r = await c_client.get(
                "/api/v1/chat",
                params={"conversation_id": conv_id, "message": "hello"},
            )
            assert r.status_code == 200
            ev1 = await asyncio.wait_for(q1.get(), timeout=1.0)
            ev2 = await asyncio.wait_for(q2.get(), timeout=1.0)
            assert ev1["type"] == "user_message"
            assert ev2["type"] == "user_message"
        finally:
            unregister_subscriber(conv_id, q1)
            unregister_subscriber(conv_id, q2)


class TestSpectateAuth:
    async def test_agent_cannot_spectate(
        self, conv_id: int, agent: str, make_staff_client
    ) -> None:
        sc = make_staff_client(agent, "agent")
        r = await sc.get(f"/staff/api/v1/conversations/{conv_id}/spectate-stream")
        assert r.status_code == 403

    async def test_senior_bus_subscriber_receives_assistant_text(
        self, c_client: AsyncClient, conv_id: int, senior: str, monkeypatch
    ) -> None:
        """senior 等价订阅效果验证：直接走 register_subscriber 拿到 assistant_text 即可。

        不打开真实 SSE 端点：ASGI in-process 跑长连会阻塞事件循环（生成器永远在 await q.get），
        端点鉴权由 test_agent_cannot_spectate 覆盖，业务投递行为由总线断言。
        """
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])
        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        q = register_subscriber(conv_id)
        try:
            await c_client.get(
                "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
            )
            # 第一帧是 user_message；assistant_text 会随后出现
            collected = await _drain_until(
                q, lambda e: e.get("type") == "assistant_text", timeout_s=1.0
            )
            assert any(e.get("type") == "assistant_text" for e in collected)
        finally:
            unregister_subscriber(conv_id, q)

    async def test_engineer_can_run_ai_tool(
        self,
        conv_id: int,
        engineer: str,
        make_staff_client,
        monkeypatch,
    ) -> None:
        """engineer 代查 query_user：应被 dispatch 到工具（这里 mock dispatch 直接返回 ok）。"""
        from ai_engine.api import staff_conversations as sc_mod

        async def _fake_dispatch(**kw):
            return {"ok": True, "data": {"user_id": kw["subject_id"]}}

        monkeypatch.setattr(sc_mod, "dispatch", _fake_dispatch)

        sc = make_staff_client(engineer, "engineer")
        r = await sc.post(
            f"/staff/api/v1/conversations/{conv_id}/ai-tools/query_user",
            json={"params": {}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["user_id"] == "U-ALPHA"

    async def test_agent_cannot_run_ai_tool(
        self, conv_id: int, agent: str, make_staff_client
    ) -> None:
        sc = make_staff_client(agent, "agent")
        r = await sc.post(
            f"/staff/api/v1/conversations/{conv_id}/ai-tools/query_user",
            json={"params": {}},
        )
        assert r.status_code == 403
