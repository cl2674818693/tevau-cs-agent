"""API: 座席会话列表 / 详情（staff_conversations.py 中的只读端点）。

覆盖：
- GET /staff/api/v1/conversations         （列表，默认 human_pending）
- GET /staff/api/v1/conversations/{id}    （单会话元信息）
- GET /staff/api/v1/transfer-candidates   （转派目标）

接管/释放/送消息/AI 草稿等写动作在 test_staff_takeover_api.py。

策略：用 init_self_db + sqlite，直接 INSERT 真数据，不 mock DAO。
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_conversations import router as staff_conv_router

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


class TestListConversationsAuth:
    """未登录 / token 非法 → 401。"""

    async def test_list_without_token_401(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/conversations")
        assert resp.status_code == 401

    async def test_list_with_bad_token_401(self, init_self_db, client) -> None:
        resp = await client.get(
            "/staff/api/v1/conversations",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert resp.status_code == 401

    async def test_list_with_bu_cookie_rejected_401(self, init_self_db, client, bu_cookie) -> None:
        """B 端 cookie 不是 staff token → 拿 cookie 没用。"""
        client.cookies.update(bu_cookie("1011010000068"))
        resp = await client.get("/staff/api/v1/conversations")
        assert resp.status_code == 401


class TestListConversationsHappyPath:
    async def test_list_default_human_pending_only(
        self, init_self_db, client, agent_headers
    ) -> None:
        """默认 status=human_pending，只返回 mode=human_pending 的会话。"""
        await insert_conversation(mode="ai")
        c2 = await insert_conversation(mode="human_pending")
        await insert_conversation(mode="human_takeover")

        resp = await client.get("/staff/api/v1/conversations", headers=agent_headers)
        assert resp.status_code == 200
        rows = resp.json()
        ids = {r["id"] for r in rows}
        assert ids == {c2}

    async def test_list_status_all_excludes_ai(
        self, init_self_db, client, agent_headers
    ) -> None:
        """status=all 含所有非 ai 会话（pending + takeover + ai_draft）。"""
        await insert_conversation(mode="ai")
        c2 = await insert_conversation(mode="human_pending")
        c3 = await insert_conversation(mode="human_takeover")
        c4 = await insert_conversation(mode="ai_draft")

        resp = await client.get(
            "/staff/api/v1/conversations?status=all", headers=agent_headers
        )
        assert resp.status_code == 200
        ids = {r["id"] for r in resp.json()}
        assert ids == {c2, c3, c4}

    async def test_list_with_risk_only(
        self, init_self_db, client, agent_headers
    ) -> None:
        """risk_only=true：会有 mode=ai 的会话因含失败回合而被列出。"""
        c_normal = await insert_conversation(mode="ai")
        c_risk = await insert_conversation(mode="ai")
        # 给 c_risk 注入一条 failed 消息
        await insert_message(c_risk, role="user", content="x", status="failed")

        resp = await client.get(
            "/staff/api/v1/conversations?risk_only=true", headers=agent_headers
        )
        assert resp.status_code == 200
        ids = {r["id"] for r in resp.json()}
        assert c_risk in ids
        assert c_normal not in ids

    async def test_list_returns_risk_flags(
        self, init_self_db, client, agent_headers
    ) -> None:
        """每行带 has_failed / has_out_of_scope / has_downvote / has_empty_tool 风险列。"""
        cid = await insert_conversation(mode="human_pending")
        resp = await client.get("/staff/api/v1/conversations", headers=agent_headers)
        assert resp.status_code == 200
        row = next(r for r in resp.json() if r["id"] == cid)
        assert "has_failed" in row
        assert "has_out_of_scope" in row
        assert "has_downvote" in row
        assert "has_empty_tool" in row


class TestGetConversationDetail:
    async def test_get_one_happy_path(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068", mode="human_pending"
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}", headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == cid
        assert body["user_type"] == "b"
        assert body["subject_id"] == "1011010000068"
        assert body["mode"] == "human_pending"

    async def test_get_one_not_found_404(
        self, init_self_db, client, agent_headers
    ) -> None:
        resp = await client.get("/staff/api/v1/conversations/9999", headers=agent_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_get_one_invalid_id_422(self, init_self_db, client, agent_headers) -> None:
        """非数字 conv_id → FastAPI 路径参数校验 422。"""
        resp = await client.get(
            "/staff/api/v1/conversations/not-a-number", headers=agent_headers
        )
        assert resp.status_code == 422

    async def test_get_one_returns_assigned_staff_when_taken(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(
            mode="human_takeover", assigned_staff_id="agent-1"
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}", headers=agent_headers
        )
        assert resp.json()["assigned_staff_id"] == "agent-1"


class TestTransferCandidates:
    async def test_candidates_excludes_self_and_inactive(
        self, init_self_db, client, agent_headers
    ) -> None:
        """active=1 的客服（除自己）出现在候选；inactive 不出现；agent 角色仅看 engineer。"""
        # agent-1 调用者（agent_headers 默认 sub=agent-1）
        await insert_staff("agent-1", "Self", "agent")  # 自己
        await insert_staff("agent-2", "Other Agent", "agent")  # 同 agent
        await insert_staff("eng-1", "Engineer A", "engineer")
        await insert_staff("eng-off", "Engineer Off", "engineer", active=0)

        resp = await client.get(
            "/staff/api/v1/transfer-candidates", headers=agent_headers
        )
        assert resp.status_code == 200
        cands = resp.json()["candidates"]
        ids = {c["staff_id"] for c in cands}
        # agent 只能转给 engineer，且不含自己 / inactive
        assert ids == {"eng-1"}

    async def test_candidates_senior_sees_all_except_self(
        self, init_self_db, client, senior_headers
    ) -> None:
        await insert_staff("senior-1", "Self", "senior")
        await insert_staff("agent-9", "A9", "agent")
        await insert_staff("eng-9", "E9", "engineer")

        resp = await client.get(
            "/staff/api/v1/transfer-candidates", headers=senior_headers
        )
        assert resp.status_code == 200
        ids = {c["staff_id"] for c in resp.json()["candidates"]}
        assert ids == {"agent-9", "eng-9"}

    async def test_candidates_requires_auth(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/transfer-candidates")
        assert resp.status_code == 401
