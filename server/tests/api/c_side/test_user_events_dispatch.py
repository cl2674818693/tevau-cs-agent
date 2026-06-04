"""Task 7: request_human 走 dispatch 路径的 TDD 新测试。

验证：
- 无人在线 → no_one_online=True，且返回体无 off_hours / next_shift_start
- 有人在线 → no_one_online=False，且会话 assigned_staff_id 已派单
"""

import pytest
import pytest_asyncio
from typing import Any
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import db, staff_presence
from ai_engine.persistence.schema import now_str


# ────────── helpers ──────────


async def _seed_online_staff(staff_id: str) -> None:
    """写 staff 表 + 上线心跳（复制 test_dispatch.py 的 _seed_staff）"""
    await db.execute(
        "INSERT INTO staff(staff_id, display_name, role, password_hash, created_at) "
        "VALUES (:i, :n, 'agent', '', :now) ON CONFLICT(staff_id) DO UPDATE SET role='agent'",
        {"i": staff_id, "n": staff_id, "now": now_str()},
    )
    await staff_presence.heartbeat(staff_id, "online")


# ────────── tests ──────────


class TestRequestHumanDispatch:
    async def test_no_one_online_returns_flag(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """无人在线：stub create_ticket 返回 no_one_online=True；
        响应体有 no_one_online=True，无 off_hours / next_shift_start。"""

        async def _fake_no_one(**kw: Any) -> dict[str, Any]:
            return {"external_ticket_id": "AI-DISP-NO-ONE", "no_one_online": True}

        monkeypatch.setattr("ai_engine.api.user_events.create_ticket_run", _fake_no_one)

        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/request-human",
            json={"reason": "test"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["no_one_online"] is True
        assert "off_hours" not in body
        assert "next_shift_start" not in body

    async def test_dispatches_to_online_staff(
        self, c_client: AsyncClient, db_ready: str, monkeypatch
    ) -> None:
        """有人在线：stub create_ticket 返回 no_one_online=False；
        响应 no_one_online=False，assigned_staff_id 已落库。"""
        await _seed_online_staff("DISP-AGENT-1")
        cid = await conv_dao.create_conversation(user_type="c", subject_id="U-ALPHA")

        async def _fake_with_agent(**kw: Any) -> dict[str, Any]:
            # 模拟 create_ticket_run 的行为：它内部会调 dispatch，这里直接派
            await db.execute(
                "UPDATE conversations SET assigned_staff_id=:s, assigned_at=:t WHERE id=:c",
                {"s": "DISP-AGENT-1", "t": now_str(), "c": kw.get("conversation_id")},
            )
            return {"external_ticket_id": "AI-DISP-AGENT", "no_one_online": False}

        monkeypatch.setattr("ai_engine.api.user_events.create_ticket_run", _fake_with_agent)

        r = await c_client.post(
            f"/api/v1/conversations/{cid}/request-human",
            json={"reason": "x"},
        )
        body = r.json()
        assert r.status_code == 200, body
        assert body["no_one_online"] is False

        row = await db.fetch_one(
            "SELECT assigned_staff_id FROM conversations WHERE id=:c", {"c": cid}
        )
        assert row["assigned_staff_id"] == "DISP-AGENT-1"
