"""chat 旁路矩阵：人工模式 / 草稿模式下，端点不再调 LLM。

矩阵：
- mode=human_takeover → 用户消息只入库 + 推客服侧；只返回 message_stop(handed_to_human)。
  不再 yield mode_change：当前 mode 已经稳定不是"切换"，硬推一帧会让前端把这帧当成新一次
  转人工反复 push 系统提示。真正的 AI→human_pending 切换由 create_ticket 工具走常驻流广播。
- mode=human_pending → 同上（同一分支）
- mode=ai_draft     → 调 collect_full_response 收草稿，落库 + 推客服侧；
                       返回 warning + message_stop(ai_draft_pending)
"""

import json

from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao

from .conftest import parse_sse, stub_run_turn


class TestChatHumanTakeover:
    async def test_handed_to_human_message_stop(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await conv_dao.set_mode(conv_id, "human_takeover", assigned_staff_id="S001")
        # 万一走到 agent loop 也 stub 一下，便于断言「没被调」
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "shouldnt"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "我还想问一句"},
        )
        frames = await parse_sse(r)
        names = [f["event"] for f in frames]
        # mode 已经稳定在 human_takeover，不该再推 mode_change（旧契约残留）
        assert "mode_change" not in names
        last = json.loads(frames[-1]["data"])
        assert last["stop_reason"] == "handed_to_human"
        assert called["n"] == 0

    async def test_user_message_persisted_in_human_mode(
        self, c_client: AsyncClient, conv_id: int
    ) -> None:
        await conv_dao.set_mode(conv_id, "human_takeover", assigned_staff_id="S001")
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "求助"},
        )
        await parse_sse(r)
        rows = await conv_dao.list_messages(conv_id)
        users = [m for m in rows if m["role"] == "user"]
        assert len(users) == 1
        assert users[0]["content"] == "求助"

    async def test_human_pending_also_bypasses_llm(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await conv_dao.set_mode(conv_id, "human_pending")
        called = {"n": 0}

        async def _run(**_kw):
            called["n"] += 1
            yield {"type": "text", "text": "x"}

        from ai_engine.api import chat as _chat

        monkeypatch.setattr(_chat.runtime, "run_turn", _run)
        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "等接管中再问一句"},
        )
        frames = await parse_sse(r)
        last = json.loads(frames[-1]["data"])
        assert last["stop_reason"] == "handed_to_human"
        assert called["n"] == 0


class TestChatAiDraftMode:
    async def test_collects_draft_and_does_not_stream_to_user(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await conv_dao.set_mode(conv_id, "ai_draft", assigned_staff_id="S002")

        # mock collect_full_response 直接返回固定草稿
        from ai_engine.agent import runtime

        async def _fake_collect(**_kw):
            return "这是 AI 草稿（不直接发给用户）"

        monkeypatch.setattr(runtime, "collect_full_response", _fake_collect)
        # run_turn 也兜底 stub，确保即使被错误地调到也不报错
        stub_run_turn(monkeypatch, [{"type": "text", "text": "X"}])

        r = await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "新的问题"},
        )
        frames = await parse_sse(r)
        # 端点应只 emit warning + message_stop(ai_draft_pending)，不应有 text_delta
        assert not any(f["event"] == "content_block_delta" for f in frames)
        last = json.loads(frames[-1]["data"])
        assert last["stop_reason"] == "ai_draft_pending"

    async def test_draft_persisted_to_messages_table(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        await conv_dao.set_mode(conv_id, "ai_draft", assigned_staff_id="S002")
        from ai_engine.agent import runtime

        async def _fake_collect(**_kw):
            return "草稿正文"

        monkeypatch.setattr(runtime, "collect_full_response", _fake_collect)
        await c_client.get(
            "/api/v1/chat",
            params={"conversation_id": conv_id, "message": "问"},
        )
        latest = await conv_dao.get_latest_ai_draft(conv_id)
        assert latest == "草稿正文"
