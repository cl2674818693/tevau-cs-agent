"""API: B 端用户提交客服评分（agent_ratings.py 中的用户端端点）。

被测端点：
- GET  /api/v1/conversations/{id}/agent-rating/eligibility
- POST /api/v1/conversations/{id}/agent-rating

身份解析：_resolve_subject(request, X-BU-ID)：
  DEV_TRUST_BU_HEADER=true → X-BU-ID 直接作 tenant_id（B 端）
  否则尝试 c_session（C 端）；最终 401。

异常矩阵：
1. 未登录（无 X-BU-ID 也无 c_session）→ 401
2. 跨 BU 提交别人会话评分 → 403
3. eligibility happy：有 assigned_staff → eligible=True
4. eligibility no staff → eligible=False
5. 评分 rating 越界（DAO 抛 ValueError）→ 400
6. 重复评分 → 409
7. 会话无客服 → 400
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.agent_ratings import router as agent_ratings_router
from ai_engine.persistence import db as db_mod
from ai_engine.persistence.schema import now_str

from .conftest import insert_conversation


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(agent_ratings_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _insert_take_action(conv_id: int, staff_id: str) -> None:
    await db_mod.execute(
        "INSERT INTO staff_actions(conversation_id, staff_id, action, at) "
        "VALUES (:c, :s, 'take', :now)",
        {"c": conv_id, "s": staff_id, "now": now_str()},
    )


class TestEligibilityAuth:
    async def test_no_subject_401(self, init_self_db, client) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.get(
            f"/api/v1/conversations/{cid}/agent-rating/eligibility"
        )
        assert resp.status_code == 401

    async def test_cross_bu_403(self, init_self_db, client, bu_headers) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.get(
            f"/api/v1/conversations/{cid}/agent-rating/eligibility",
            headers=bu_headers("1011010000189"),
        )
        assert resp.status_code == 403


class TestEligibilityHappy:
    async def test_no_assigned_staff_returns_not_eligible(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.get(
            f"/api/v1/conversations/{cid}/agent-rating/eligibility",
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"eligible": False, "already_rated": False, "staff_id": None}

    async def test_with_assigned_staff_eligible(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b",
            subject_id="1011010000068",
            mode="human_takeover",
            assigned_staff_id="agent-1",
        )
        resp = await client.get(
            f"/api/v1/conversations/{cid}/agent-rating/eligibility",
            headers=bu_headers("1011010000068"),
        )
        body = resp.json()
        assert body["eligible"] is True
        assert body["already_rated"] is False
        assert body["staff_id"] == "agent-1"

    async def test_fallback_to_last_take_action(
        self, init_self_db, client, bu_headers
    ) -> None:
        """assigned_staff_id 清空（已 release）但有 take 历史 → 仍 eligible，
        staff_id 回退到最近一次 take 的客服。"""
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068", mode="ai",
        )
        await _insert_take_action(cid, "agent-99")
        resp = await client.get(
            f"/api/v1/conversations/{cid}/agent-rating/eligibility",
            headers=bu_headers("1011010000068"),
        )
        body = resp.json()
        assert body["eligible"] is True
        assert body["staff_id"] == "agent-99"


class TestSubmitRating:
    async def test_submit_happy(self, init_self_db, client, bu_headers) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5, "comment": "great"},
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "id" in body

    async def test_submit_no_staff_400(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(user_type="b", subject_id="1011010000068")
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5},
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 400
        assert "no agent" in resp.json()["detail"]

    async def test_submit_invalid_rating_400(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 7, "comment": "x"},
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 400
        assert "1..5" in resp.json()["detail"]

    async def test_submit_already_rated_409(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        r1 = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5},
            headers=bu_headers("1011010000068"),
        )
        assert r1.status_code == 200
        r2 = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 4},
            headers=bu_headers("1011010000068"),
        )
        assert r2.status_code == 409
        assert "already rated" in r2.json()["detail"]

    async def test_submit_unauthenticated_401(
        self, init_self_db, client
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5},
        )
        assert resp.status_code == 401

    async def test_submit_cross_bu_403(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"rating": 5},
            headers=bu_headers("1011010000189"),
        )
        assert resp.status_code == 403

    async def test_submit_missing_rating_field_422(
        self, init_self_db, client, bu_headers
    ) -> None:
        cid = await insert_conversation(
            user_type="b", subject_id="1011010000068",
            mode="human_takeover", assigned_staff_id="agent-1",
        )
        resp = await client.post(
            f"/api/v1/conversations/{cid}/agent-rating",
            json={"comment": "no rating"},
            headers=bu_headers("1011010000068"),
        )
        assert resp.status_code == 422
