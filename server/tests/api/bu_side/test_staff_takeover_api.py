"""API: 座席接管 / 释放 / 解决 / 转派 / 发消息 / AI 草稿（staff_conversations.py 写动作）。

被测端点：
- POST /staff/api/v1/conversations/{id}/take
- POST /staff/api/v1/conversations/{id}/release
- POST /staff/api/v1/conversations/{id}/resolve
- POST /staff/api/v1/conversations/{id}/transfer-to/{target}
- POST /staff/api/v1/conversations/{id}/messages
- POST /staff/api/v1/conversations/{id}/ai-draft/enable / disable / approve / reject
- POST /staff/api/v1/conversations/{id}/ai-tools/{tool_name}（仅 senior/engineer）

异常矩阵重点：
- 双客服并发接管 → 一个 200 一个 409
- 已接管的会话再次接管 → 409
- 释放非自己接管的会话 → 409
- agent 转派给 senior → 403（agent 仅可转 engineer）
- 转派目标不存在 → 404
- send_message 空 body → 422
- send_message 给非自己的会话 → 403
- ai-tools 非 senior/engineer → 403
"""

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from ai_engine.api.staff_conversations import router as staff_conv_router
from ai_engine.persistence.db import get_conn

from .conftest import insert_conversation, insert_message, insert_staff


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_conv_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _get_conv_row(cid: int) -> dict:
    async with get_conn() as conn:
        res = await conn.execute(
            text("SELECT mode, assigned_staff_id FROM conversations WHERE id=:id"),
            {"id": cid},
        )
        r = res.mappings().first()
    return dict(r) if r else {}


class TestTake:
    async def test_take_idle_conversation(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(mode="human_pending")
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/take", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        row = await _get_conv_row(cid)
        assert row["mode"] == "human_takeover"
        assert row["assigned_staff_id"] == "agent-1"

    async def test_take_already_taken_409(
        self, init_self_db, client, agent_headers, agent2_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        # agent-2 来抢
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/take", headers=agent2_headers
        )
        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"]

    async def test_take_writes_staff_action_log(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(mode="human_pending")
        await client.post(
            f"/staff/api/v1/conversations/{cid}/take", headers=agent_headers
        )
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT action, staff_id FROM staff_actions WHERE conversation_id=:c"),
                {"c": cid},
            )
            rows = [dict(r) for r in res.mappings().all()]
        assert any(r["action"] == "take" and r["staff_id"] == "agent-1" for r in rows)

    async def test_concurrent_take_one_wins(
        self, init_self_db, client, agent_headers, agent2_headers
    ) -> None:
        """两个客服同时 take 同一会话：一个 200 一个 409。
        SQLite 单连串行化执行，但 UPDATE 的 WHERE assigned_staff_id IS NULL 保证只能成功一次。"""
        cid = await insert_conversation(mode="human_pending")
        r1, r2 = await asyncio.gather(
            client.post(f"/staff/api/v1/conversations/{cid}/take", headers=agent_headers),
            client.post(
                f"/staff/api/v1/conversations/{cid}/take", headers=agent2_headers
            ),
        )
        codes = sorted([r1.status_code, r2.status_code])
        assert codes == [200, 409]

    async def test_take_requires_auth(self, init_self_db, client) -> None:
        cid = await insert_conversation(mode="human_pending")
        resp = await client.post(f"/staff/api/v1/conversations/{cid}/take")
        assert resp.status_code == 401


class TestRelease:
    async def test_release_own_conversation(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/release", headers=agent_headers
        )
        assert resp.status_code == 200
        row = await _get_conv_row(cid)
        assert row["mode"] == "ai"
        assert row["assigned_staff_id"] is None

    async def test_release_not_assigned_to_me_409(
        self, init_self_db, client, agent2_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        # agent-2 想 release agent-1 的会话 → 409
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/release", headers=agent2_headers
        )
        assert resp.status_code == 409

    async def test_release_ai_conversation_409(
        self, init_self_db, client, agent_headers
    ) -> None:
        """mode=ai 的会话没人接管 → release 没匹配行 → 409。"""
        cid = await insert_conversation(mode="ai")
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/release", headers=agent_headers
        )
        assert resp.status_code == 409


class TestResolve:
    async def test_resolve_own_conversation(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/resolve", headers=agent_headers
        )
        assert resp.status_code == 200
        row = await _get_conv_row(cid)
        assert row["mode"] == "ai"
        # 记录 resolved 动作
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT action FROM staff_actions WHERE conversation_id=:c"),
                {"c": cid},
            )
            actions = {r[0] for r in res.fetchall()}
        assert "resolved" in actions

    async def test_resolve_not_assigned_to_me_409(
        self, init_self_db, client, agent2_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/resolve", headers=agent2_headers
        )
        assert resp.status_code == 409


class TestTransferTo:
    async def test_transfer_to_engineer_happy(
        self, init_self_db, client, agent_headers
    ) -> None:
        await insert_staff("eng-1", "E1", "engineer")
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/eng-1",
            headers=agent_headers,
        )
        assert resp.status_code == 200
        row = await _get_conv_row(cid)
        assert row["assigned_staff_id"] == "eng-1"
        assert row["mode"] == "human_takeover"

    async def test_transfer_target_not_found_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/ghost",
            headers=agent_headers,
        )
        assert resp.status_code == 404

    async def test_transfer_inactive_target_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        await insert_staff("eng-off", "E off", "engineer", active=0)
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/eng-off",
            headers=agent_headers,
        )
        assert resp.status_code == 404

    async def test_agent_cannot_transfer_to_senior_403(
        self, init_self_db, client, agent_headers
    ) -> None:
        await insert_staff("senior-9", "S9", "senior")
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/senior-9",
            headers=agent_headers,
        )
        assert resp.status_code == 403

    async def test_transfer_not_assigned_to_me_409(
        self, init_self_db, client, agent2_headers
    ) -> None:
        await insert_staff("eng-1", "E1", "engineer")
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/eng-1",
            headers=agent2_headers,
        )
        assert resp.status_code == 409


class TestSendMessage:
    async def test_send_message_happy(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        await insert_staff("agent-1", "Agent One", "agent")  # 有 display_name 才能广播
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "hello user"},
            headers=agent_headers,
        )
        assert resp.status_code == 200

    async def test_send_message_empty_body_422(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "   "},
            headers=agent_headers,
        )
        assert resp.status_code == 422

    async def test_send_message_not_my_conversation_403(
        self, init_self_db, client, agent2_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "hi"},
            headers=agent2_headers,
        )
        assert resp.status_code == 403

    async def test_send_message_when_mode_not_takeover_403(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "hi"},
            headers=agent_headers,
        )
        assert resp.status_code == 403


class TestAiDraftFlow:
    async def test_enable_then_disable(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(mode="ai")
        r1 = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/enable", headers=agent_headers
        )
        assert r1.status_code == 200
        row = await _get_conv_row(cid)
        assert row["mode"] == "ai_draft"
        assert row["assigned_staff_id"] == "agent-1"

        r2 = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/disable", headers=agent_headers
        )
        assert r2.status_code == 200
        row = await _get_conv_row(cid)
        assert row["mode"] == "ai"

    async def test_approve_no_draft_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve", headers=agent_headers
        )
        assert resp.status_code == 404

    async def test_approve_happy(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        # 注入一条 ai_draft 行
        await insert_message(cid, role="ai_draft", content="draft text")
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve", headers=agent_headers
        )
        assert resp.status_code == 200
        # draft 被清，assistant 行已写入
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT role, content FROM messages WHERE conversation_id=:c ORDER BY id"),
                {"c": cid},
            )
            rows = [dict(r) for r in res.mappings().all()]
        roles = [r["role"] for r in rows]
        assert "assistant" in roles
        assert "ai_draft" not in roles

    async def test_reject_happy(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        await insert_message(cid, role="ai_draft", content="draft text")
        await insert_staff("agent-1", "Agent One", "agent")
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/reject",
            json={"rewrite": "客服改写后的回复"},
            headers=agent_headers,
        )
        assert resp.status_code == 200

    async def test_reject_no_draft_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/reject",
            json={"rewrite": "x"},
            headers=agent_headers,
        )
        assert resp.status_code == 404

    async def test_approve_not_my_conversation_403(
        self, init_self_db, client, agent2_headers
    ) -> None:
        cid = await insert_conversation(
            mode="ai_draft", assigned_staff_id="agent-1"
        )
        await insert_message(cid, role="ai_draft", content="x")
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve",
            headers=agent2_headers,
        )
        assert resp.status_code == 403


class TestRunAiTool:
    async def test_agent_forbidden(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {}},
            headers=agent_headers,
        )
        assert resp.status_code == 403

    async def test_engineer_conv_not_found_404(
        self, init_self_db, client, engineer_headers, monkeypatch
    ) -> None:
        # 防止 dispatch 真去打业务库
        monkeypatch.setattr(
            "ai_engine.api.staff_conversations.dispatch",
            AsyncMock(return_value={"ok": True}),
        )
        resp = await client.post(
            "/staff/api/v1/conversations/9999/ai-tools/query_user",
            json={"params": {}},
            headers=engineer_headers,
        )
        assert resp.status_code == 404

    async def test_engineer_happy_path(
        self, init_self_db, client, engineer_headers, monkeypatch
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="U123")
        monkeypatch.setattr(
            "ai_engine.api.staff_conversations.dispatch",
            AsyncMock(return_value={"data": {"hello": "world"}}),
        )
        resp = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {"user_id": "U123"}},
            headers=engineer_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"data": {"hello": "world"}}
