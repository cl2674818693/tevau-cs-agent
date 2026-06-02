"""E2E 剧本 #5：多座席协作场景（接管 / 转派 / 抢接 / 释放）。

剧本梗概：
    1. 用户求人工 → mode=human_pending。
    2. A、B 两个座席同时调 take —— 第一个 200，第二个 409（原子接管不重复）。
    3. A 调 transfer-to/B → 会话转给 B；A 的 staff_actions=transfer_out，B 的=take。
    4. B 又调 release → 回 mode=ai，assigned_staff_id=NULL；后续可再次 take。
    5. agent 角色试图转给 senior → 403（仅 engineer 可作为 agent 转派目标）。
    6. 用户再求人工 → 新 pending；C 抢接 → 成功；再发消息 → human_message 广播。
    7. transfer-candidates 端点：agent 看到的候选只含 engineer；senior/engineer 看到全部。

异常分支：
    - 非分派座席调 release / transfer → 409。
    - 转派目标不存在或 inactive → 404。
"""

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao

from .conftest import insert_staff_row


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    cid = int(r.json()["conversation_id"])
    await c_client.post(
        f"/api/v1/conversations/{cid}/request-human", json={"reason": "x"}
    )
    return cid


@pytest_asyncio.fixture
async def crew(db_ready) -> dict[str, str]:
    """4 个座席：2 agent + 1 senior + 1 engineer。"""
    await insert_staff_row("agent-A", "Agent A", "agent")
    await insert_staff_row("agent-B", "Agent B", "agent")
    await insert_staff_row("senior-1", "Senior One", "senior")
    await insert_staff_row("eng-1", "Engineer One", "engineer")
    return {"agentA": "agent-A", "agentB": "agent-B", "senior": "senior-1", "eng": "eng-1"}


class TestRaceTake:
    async def test_two_staff_race_only_one_wins(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        b = make_staff_client(crew["agentB"], "agent")
        # 顺序 take，第二个必须 409（接管原子性 by `WHERE assigned_staff_id IS NULL`）
        r1 = await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r2 = await b.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r1.status_code == 200
        assert r2.status_code == 409
        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "human_takeover"
        assert sid == crew["agentA"]


class TestTransferTo:
    async def test_engineer_can_be_target_of_agent_transfer(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r = await a.post(
            f"/staff/api/v1/conversations/{conv_id}/transfer-to/{crew['eng']}"
        )
        assert r.status_code == 200
        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "human_takeover"
        assert sid == crew["eng"]

    async def test_agent_cannot_transfer_to_senior(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r = await a.post(
            f"/staff/api/v1/conversations/{conv_id}/transfer-to/{crew['senior']}"
        )
        assert r.status_code == 403

    async def test_transfer_to_nonexistent_returns_404(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r = await a.post(
            f"/staff/api/v1/conversations/{conv_id}/transfer-to/nonexistent-id"
        )
        assert r.status_code == 404

    async def test_non_assignee_cannot_transfer(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        b = make_staff_client(crew["agentB"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        # B 不是当前指派人
        r = await b.post(
            f"/staff/api/v1/conversations/{conv_id}/transfer-to/{crew['eng']}"
        )
        assert r.status_code == 409


class TestReleaseAndReclaim:
    async def test_release_clears_assignment_and_allows_re_take(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r = await a.post(f"/staff/api/v1/conversations/{conv_id}/release")
        assert r.status_code == 200
        mode, sid = await conv_dao.get_mode(conv_id)
        assert mode == "ai"
        assert sid is None

        # B 现在可以接管（注意 take 端点要求 mode=human_pending 才走候选列表，
        # 但实际更新 SQL 只要 assigned_staff_id IS NULL 就允许更新到 human_takeover）
        b = make_staff_client(crew["agentB"], "agent")
        r = await b.post(f"/staff/api/v1/conversations/{conv_id}/take")
        assert r.status_code == 200
        _, sid2 = await conv_dao.get_mode(conv_id)
        assert sid2 == crew["agentB"]

    async def test_non_assignee_release_returns_409(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        b = make_staff_client(crew["agentB"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")
        r = await b.post(f"/staff/api/v1/conversations/{conv_id}/release")
        assert r.status_code == 409


class TestTransferCandidates:
    async def test_agent_sees_only_engineers(
        self, crew, make_staff_client
    ) -> None:
        a = make_staff_client(crew["agentA"], "agent")
        r = await a.get("/staff/api/v1/transfer-candidates")
        assert r.status_code == 200
        candidates = r.json()["candidates"]
        roles = {c["role"] for c in candidates}
        assert roles == {"engineer"}
        ids = {c["staff_id"] for c in candidates}
        assert crew["eng"] in ids
        assert crew["agentA"] not in ids  # 排除自己

    async def test_senior_sees_all_other_active(
        self, crew, make_staff_client
    ) -> None:
        s = make_staff_client(crew["senior"], "senior")
        r = await s.get("/staff/api/v1/transfer-candidates")
        assert r.status_code == 200
        ids = {c["staff_id"] for c in r.json()["candidates"]}
        assert crew["agentA"] in ids
        assert crew["agentB"] in ids
        assert crew["eng"] in ids
        assert crew["senior"] not in ids


class TestTransferBroadcast:
    async def test_transfer_publishes_event(
        self, conv_id: int, crew, make_staff_client
    ) -> None:
        from ai_engine.api.staff_conversations import (
            register_subscriber,
            unregister_subscriber,
        )

        a = make_staff_client(crew["agentA"], "agent")
        await a.post(f"/staff/api/v1/conversations/{conv_id}/take")

        q = register_subscriber(conv_id)
        try:
            r = await a.post(
                f"/staff/api/v1/conversations/{conv_id}/transfer-to/{crew['eng']}"
            )
            assert r.status_code == 200
            import asyncio as _aio

            ev = await _aio.wait_for(q.get(), timeout=1.0)
            assert ev["type"] == "transferred"
            assert ev["to_staff_id"] == crew["eng"]
        finally:
            unregister_subscriber(conv_id, q)
