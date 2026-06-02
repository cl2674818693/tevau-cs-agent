"""API: 留痕只读端点（staff_logs.py）。

被测端点：
- GET /staff/api/v1/conversations/{id}/messages          会话消息历史（分页）
- GET /staff/api/v1/conversations/{id}/tool-audits       会话工具审计
- GET /staff/api/v1/conversations/{id}/feedback          会话反馈
- GET /staff/api/v1/audits/recent                        跨会话审计流（筛选 + 页码）

异常矩阵：
1. 未登录 → 401
2. 会话存在 → 200 + 消息体
3. 会话不存在 → 200 + 空列表（端点不强校验存在）
4. 分页 limit 越界 → 422
5. 跨会话审计：筛选/页码工作
"""

import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_logs import router as staff_logs_router
from ai_engine.persistence import audit as audit_dao
from ai_engine.persistence import feedback as fb_dao

from .conftest import insert_conversation, insert_message


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_logs_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestConversationMessages:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        cid = await insert_conversation()
        resp = await client.get(f"/staff/api/v1/conversations/{cid}/messages")
        assert resp.status_code == 401

    async def test_messages_returned(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        for i in range(3):
            await insert_message(cid, role="user", content=f"hello-{i}")
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/messages", headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["conversation_id"] == cid
        assert len(body["messages"]) == 3
        assert body["messages"][0]["content"] == "hello-0"
        assert body["messages"][-1]["content"] == "hello-2"
        assert "has_more" in body
        # 每条带 attachments 字段（空列表）
        for m in body["messages"]:
            assert m["attachments"] == []

    async def test_assistant_content_extracted_to_text(
        self, init_self_db, client, agent_headers
    ) -> None:
        """assistant 入库是 content-block JSON，留痕展示需还原纯文本。"""
        cid = await insert_conversation()
        blocks = json.dumps([{"type": "text", "text": "answer"}])
        await insert_message(cid, role="assistant", content=blocks)
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/messages", headers=agent_headers
        )
        m = resp.json()["messages"][0]
        assert m["content"] == "answer"

    async def test_limit_validation_too_high(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/messages?limit=999", headers=agent_headers
        )
        assert resp.status_code == 422

    async def test_limit_validation_too_low(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/messages?limit=0", headers=agent_headers
        )
        assert resp.status_code == 422

    async def test_pagination_before_id(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        ids = [await insert_message(cid, content=f"m-{i}") for i in range(5)]
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/messages?limit=2&before_id={ids[3]}",
            headers=agent_headers,
        )
        body = resp.json()
        assert resp.status_code == 200
        # 取 id < ids[3] 的最新 2 条，升序返回 → ids[1], ids[2]
        returned = [m["id"] for m in body["messages"]]
        assert returned == [ids[1], ids[2]]
        assert body["has_more"] is True  # 满页启发式

    async def test_messages_for_nonexistent_conv_empty(
        self, init_self_db, client, agent_headers
    ) -> None:
        """端点不校验会话存在，无消息直接返空列表（运营查无效 ID 不应 404 误导）。"""
        resp = await client.get(
            "/staff/api/v1/conversations/99999/messages", headers=agent_headers
        )
        assert resp.status_code == 200
        assert resp.json()["messages"] == []


class TestConversationToolAudits:
    async def test_unauthenticated_401(self, init_self_db, client) -> None:
        cid = await insert_conversation()
        resp = await client.get(f"/staff/api/v1/conversations/{cid}/tool-audits")
        assert resp.status_code == 401

    async def test_audits_returned(self, init_self_db, client, agent_headers) -> None:
        cid = await insert_conversation()
        await audit_dao.log_tool_call(
            conversation_id=cid,
            tool_name="query_user",
            params={"q": "x"},
            result_size=42,
            duration_ms=10,
            rejected=False,
            reject_reason=None,
            is_empty=False,
        )
        await audit_dao.log_tool_call(
            conversation_id=cid,
            tool_name="search_code",
            params={"k": "y"},
            result_size=0,
            duration_ms=5,
            rejected=True,
            reject_reason="cooldown",
            is_empty=True,
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/tool-audits", headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        names = [a["tool_name"] for a in body["audits"]]
        assert names == ["query_user", "search_code"]


class TestConversationFeedback:
    async def test_feedback_returned(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation(user_type="c", subject_id="U1")
        mid = await insert_message(cid, role="assistant", content="x")
        await fb_dao.add_feedback(
            conversation_id=cid,
            message_id=mid,
            rating="down",
            reason="not helpful",
            subject_id="U1",
            user_type="c",
        )
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/feedback", headers=agent_headers
        )
        assert resp.status_code == 200
        fbs = resp.json()["feedback"]
        assert len(fbs) == 1
        assert fbs[0]["rating"] == "down"

    async def test_feedback_empty_when_none(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        resp = await client.get(
            f"/staff/api/v1/conversations/{cid}/feedback", headers=agent_headers
        )
        assert resp.json()["feedback"] == []


class TestRecentAudits:
    async def test_recent_audits_default(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        for i in range(3):
            await audit_dao.log_tool_call(
                conversation_id=cid,
                tool_name=f"tool-{i}",
                params={"i": i},
                result_size=0,
                duration_ms=1,
                rejected=False,
                reject_reason=None,
            )
        resp = await client.get(
            "/staff/api/v1/audits/recent", headers=agent_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["limit"] == 100
        # 最新在前
        assert body["audits"][0]["tool_name"] == "tool-2"

    async def test_recent_audits_rejected_only(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t1", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None,
        )
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t2", params={}, result_size=0,
            duration_ms=0, rejected=True, reject_reason="x",
        )
        resp = await client.get(
            "/staff/api/v1/audits/recent?rejected=true", headers=agent_headers
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["audits"][0]["tool_name"] == "t2"

    async def test_recent_audits_filter_by_tool(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="query_user", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None,
        )
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="search_code", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None,
        )
        resp = await client.get(
            "/staff/api/v1/audits/recent?tool_name=query_user", headers=agent_headers
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["audits"][0]["tool_name"] == "query_user"

    async def test_recent_audits_empty_only(
        self, init_self_db, client, agent_headers
    ) -> None:
        cid = await insert_conversation()
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t1", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None, is_empty=False,
        )
        await audit_dao.log_tool_call(
            conversation_id=cid, tool_name="t2", params={}, result_size=0,
            duration_ms=0, rejected=False, reject_reason=None, is_empty=True,
        )
        resp = await client.get(
            "/staff/api/v1/audits/recent?empty_only=true", headers=agent_headers
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["audits"][0]["tool_name"] == "t2"

    async def test_recent_audits_unauth_401(self, init_self_db, client) -> None:
        resp = await client.get("/staff/api/v1/audits/recent")
        assert resp.status_code == 401

    async def test_limit_validation(self, init_self_db, client, agent_headers) -> None:
        resp = await client.get(
            "/staff/api/v1/audits/recent?limit=500", headers=agent_headers
        )
        assert resp.status_code == 422
