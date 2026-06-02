"""C 端消息反馈：/api/v1/conversations/{cid}/feedback。

被测要点：
- rating ∈ {up, down}，越界 400
- up：写库 + 计数；不触发 Lark / needs_review
- down：写库 + needs_review=1 + 尝试 Lark（Lark 故障不阻断）
- 归属校验复用 chat._authorize_conversation：跨用户 / 未登录 → 403
"""

from typing import Any

import pytest
from httpx import AsyncClient

from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence import feedback as fb_dao

from .conftest import TOKEN_B, auth_headers


@pytest.fixture
def _mute_lark(monkeypatch) -> list[dict[str, Any]]:
    """捕获 Lark 调用而不真发；返回收到的 payload 列表。"""
    seen: list[dict[str, Any]] = []

    async def _fake(payload: dict[str, Any]) -> None:
        seen.append(payload)

    monkeypatch.setattr("ai_engine.api.feedback._notify_lark", _fake)
    return seen


class TestFeedbackHappyPath:
    async def test_up_persists_without_needs_review(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1, "rating": "up"},
        )
        assert r.status_code == 200 and r.json() == {"ok": True}
        # needs_review 仍为 0
        from ai_engine.persistence.db import fetch_one

        row = await fetch_one(
            "SELECT needs_review FROM conversations WHERE id=:id", {"id": conv_id}
        )
        assert row["needs_review"] == 0
        # Lark 不触发
        assert _mute_lark == []

    async def test_down_marks_needs_review_and_pings_lark(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 7, "rating": "down", "reason": "答错了"},
        )
        assert r.status_code == 200
        from ai_engine.persistence.db import fetch_one

        row = await fetch_one(
            "SELECT needs_review FROM conversations WHERE id=:id", {"id": conv_id}
        )
        assert row["needs_review"] == 1
        # Lark 收到一条
        assert len(_mute_lark) == 1
        text = _mute_lark[0]["text"]
        assert "差评" in text and "答错了" in text

    async def test_down_persists_even_if_lark_fails(
        self, c_client: AsyncClient, conv_id: int, monkeypatch
    ) -> None:
        """Lark 抛错 → 反馈仍 ok（Lark 是尽力而为）。"""

        async def _boom(_p):
            raise RuntimeError("lark down")

        monkeypatch.setattr("ai_engine.api.feedback._notify_lark", _boom)
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1, "rating": "down"},
        )
        assert r.status_code == 200
        # 仍应落 needs_review
        from ai_engine.persistence.db import fetch_one

        row = await fetch_one(
            "SELECT needs_review FROM conversations WHERE id=:id", {"id": conv_id}
        )
        assert row["needs_review"] == 1

    async def test_feedback_row_persisted(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 42, "rating": "up", "reason": "棒"},
        )
        # 反查 message_feedback
        rows = await fb_dao.list_feedback(conv_id)
        assert rows and rows[0]["message_id"] == 42


class TestFeedbackValidation:
    async def test_invalid_rating_returns_400(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1, "rating": "meh"},
        )
        assert r.status_code == 400

    async def test_missing_rating_returns_422(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1},
        )
        assert r.status_code == 422

    async def test_missing_message_id_returns_422(
        self, c_client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await c_client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"rating": "up"},
        )
        assert r.status_code == 422


class TestFeedbackAuth:
    async def test_other_user_forbidden(
        self, client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1, "rating": "up"},
            headers=auth_headers(TOKEN_B),
        )
        assert r.status_code == 403

    async def test_guest_forbidden(
        self, client: AsyncClient, conv_id: int, _mute_lark
    ) -> None:
        r = await client.post(
            f"/api/v1/conversations/{conv_id}/feedback",
            json={"message_id": 1, "rating": "up"},
        )
        assert r.status_code == 403

    async def test_nonexistent_conversation_forbidden(
        self, c_client: AsyncClient, _mute_lark
    ) -> None:
        r = await c_client.post(
            "/api/v1/conversations/9999999/feedback",
            json={"message_id": 1, "rating": "up"},
        )
        assert r.status_code == 403
