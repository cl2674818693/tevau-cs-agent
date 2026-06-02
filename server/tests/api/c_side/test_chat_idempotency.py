"""chat 幂等：client_message_id 命中已完成回合 → 重放历史 assistant 文本，不再调 LLM。

源码路径：chat._duplicate_turn_id → conv_dao.find_completed_turn → _replay_turn

构造方式：直接在 messages 表里写一条已完成的 user 行（status=done、带 client_message_id）
+ 紧跟一条 assistant 行（json blocks）。再用同样的 client_message_id 打 /api/v1/chat，
应收到重放帧而不触发 runtime.run_turn。
"""

import json

from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao

from .conftest import parse_sse


async def _seed_completed_turn(
    conv_id: int, client_message_id: str, assistant_text: str
) -> int:
    """直接落库一对 user(done)+assistant，模拟"上一次已完成的回合"。"""
    uid = await conv_dao.append_user_turn(conv_id, "原始提问", client_message_id)
    await conv_dao.finalize_turn(uid, "done")
    await conv_dao.append_message(
        conv_id, "assistant", json.dumps([{"type": "text", "text": assistant_text}])
    )
    return uid


class TestIdempotencyReplay:
    async def test_replay_same_client_message_id(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await _seed_completed_turn(conv_id, "cmid-A", "上一次的回答")
        # 任何对 run_turn 的调用都视为失败（应当不被触达）
        called = {"n": 0}

        async def _boom(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "should-not-stream"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _boom)
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "再问一次",
                "client_message_id": "cmid-A",
            },
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        # 重放帧：message_start → content_block_delta(原文本) → message_stop(replayed)
        texts = [
            json.loads(f["data"])["delta"]["text"]
            for f in frames
            if f["event"] == "content_block_delta"
        ]
        assert "上一次的回答" in "".join(texts)
        last = json.loads(frames[-1]["data"])
        assert last["stop_reason"] == "replayed"
        assert called["n"] == 0

    async def test_no_replay_when_client_message_id_omitted(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await _seed_completed_turn(conv_id, "cmid-B", "旧回答")
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "新回答"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "x"},
        )
        await parse_sse(r)
        assert called["n"] == 1  # 未传 client_message_id → 走 agent loop

    async def test_no_replay_when_id_differs(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await _seed_completed_turn(conv_id, "cmid-OLD", "旧回答")
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "新回答"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)
        await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "x",
                "client_message_id": "cmid-NEW",
            },
        )
        assert called["n"] == 1

    async def test_no_replay_when_prior_turn_failed(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        # 写一条 status=failed 的 user 行：find_completed_turn 不命中
        uid = await conv_dao.append_user_turn(conv_id, "boom", "cmid-FAIL")
        await conv_dao.finalize_turn(uid, "failed", "INTERNAL_ERROR")
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "retry"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)
        await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "再试",
                "client_message_id": "cmid-FAIL",
            },
        )
        assert called["n"] == 1

    async def test_replay_when_multi_assistant_blocks(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """一个 user 回合后可能有多条 assistant（多次工具→多段文本）。重放应全量。"""
        uid = await conv_dao.append_user_turn(conv_id, "原始", "cmid-MULTI")
        await conv_dao.finalize_turn(uid, "done")
        await conv_dao.append_message(
            conv_id, "assistant", json.dumps([{"type": "text", "text": "第一段。"}])
        )
        await conv_dao.append_message(
            conv_id, "assistant", json.dumps([{"type": "text", "text": "第二段。"}])
        )
        from ai_engine.api import chat as _chat

        async def _boom(**_kw):
            raise AssertionError("should not call LLM")
            yield  # noqa: unreachable

        monkeypatch.setattr(_chat.runtime, "run_turn", _boom)
        r = await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": conv_id,
                "message": "再问",
                "client_message_id": "cmid-MULTI",
            },
        )
        frames = await parse_sse(r)
        joined = "".join(
            json.loads(f["data"])["delta"]["text"]
            for f in frames
            if f["event"] == "content_block_delta"
        )
        # 多条 assistant 应都被重放
        assert "第一段。" in joined and "第二段。" in joined

    async def test_replay_isolated_per_conversation(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """同一 client_message_id 在另一会话不应命中重放（按 conversation_id 隔离）。"""
        # 给当前会话埋上 cmid-X 的已完成回合
        await _seed_completed_turn(conv_id, "cmid-X", "原回答")
        # 新建另一会话，用同 cmid 提问 → 应走真路径
        from ai_engine.persistence.conversations import create_conversation

        other_cid = await create_conversation("c", "U-ALPHA")
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "fresh"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)
        await c_client.get(
            "/api/v1/chat",
            params={
                "conversation_id": other_cid,
                "message": "x",
                "client_message_id": "cmid-X",
            },
        )
        assert called["n"] == 1
