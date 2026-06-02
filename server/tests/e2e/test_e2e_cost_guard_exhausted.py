"""E2E 剧本 #10：当日 token 配额耗尽 → 入口硬闸 + 提示用户。

剧本梗概：
    1. 把 daily_token_limit 调到 100；直接落 by-model 表里写入超过额度的累计。
    2. 用户调 chat：is_exhausted=True → 立即 yield warning("额度已用完") +
       message_stop(budget_exceeded)；主 LLM 不被调。
    3. 80% 提醒：累计 = 80% 时用户发消息 → 主 LLM 正常被调，期间触发
       system 事件（warning）。
    4. 不同 subject_id 配额独立：B 端不受 C 端用满影响。

异常分支：
    - 不超额时仍能正常 chat（正向验证开关未误触发）。
"""

import pytest_asyncio
from httpx import AsyncClient

from ai_engine.config import settings

from .conftest import event_data, parse_sse, stub_run_turn


@pytest_asyncio.fixture
def tight_budget(monkeypatch):
    monkeypatch.setattr(settings, "daily_token_limit", 100, raising=False)


async def _seed_usage(subject_id: str, user_type: str, in_tok: int, out_tok: int) -> None:
    """直接走 token_budget._record 累加（upsert，二次调用会增量而非冲突）。"""
    from datetime import UTC, datetime

    from ai_engine.governance.token_budget import _record

    day = datetime.now(UTC).date().isoformat()
    await _record(subject_id, user_type, day, in_tok, out_tok, model="claude-sonnet-4-6")


@pytest_asyncio.fixture
async def conv_id(c_client: AsyncClient) -> int:
    r = await c_client.post("/api/v1/conversations", json={})
    return int(r.json()["conversation_id"])


class TestCostGuard:
    async def test_exhausted_blocks_ai_and_emits_warning(
        self, c_client: AsyncClient, conv_id: int, tight_budget, monkeypatch
    ) -> None:
        """超额 → 立刻给 warning + stop(budget_exceeded)，不进 LLM。"""
        await _seed_usage("U-ALPHA", "c", 80, 30)  # 110 > 100

        ai_called = {"n": 0}

        def _stub(**kw):
            ai_called["n"] += 1
            return [{"type": "text", "text": "won't run"}]

        stub_run_turn(monkeypatch, _stub)

        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        warnings = event_data(frames, "warning")
        assert any("额度已用完" in w["text"] for w in warnings)
        stops = event_data(frames, "message_stop")
        assert any(s.get("stop_reason") == "budget_exceeded" for s in stops)
        assert ai_called["n"] == 0

    async def test_unexhausted_still_proceeds(
        self, c_client: AsyncClient, conv_id: int, tight_budget, monkeypatch
    ) -> None:
        """额度未满 → 正常 chat。"""
        await _seed_usage("U-ALPHA", "c", 10, 5)  # 15 < 100
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok"}])
        r = await c_client.get(
            "/api/v1/chat", params={"conversation_id": conv_id, "message": "hi"}
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        deltas = event_data(frames, "content_block_delta")
        all_text = "".join(d["delta"]["text"] for d in deltas)
        assert "ok" in all_text

    async def test_different_subject_unaffected(
        self, bu_client: AsyncClient, tight_budget, monkeypatch
    ) -> None:
        """C 端用满 → B 端自己 conv 不受影响。"""
        await _seed_usage("U-ALPHA", "c", 500, 0)  # C 端超额
        stub_run_turn(monkeypatch, [{"type": "text", "text": "ok-b"}])

        # B 端开会话 + 发消息
        r = await bu_client.post("/api/v1/conversations", json={})
        cid = int(r.json()["conversation_id"])
        r = await bu_client.get(
            "/api/v1/chat", params={"conversation_id": cid, "message": "hi"}
        )
        assert r.status_code == 200
        frames = await parse_sse(r)
        warnings = event_data(frames, "warning")
        assert not [w for w in warnings if "额度已用完" in w["text"]]
        # 文本能正常流出
        deltas = event_data(frames, "content_block_delta")
        all_text = "".join(d["delta"]["text"] for d in deltas)
        assert "ok-b" in all_text

    async def test_is_exhausted_function_direct(self, db_ready, tight_budget) -> None:
        """直接调 is_exhausted 验证阈值边界。"""
        from ai_engine.governance.token_budget import is_exhausted

        assert await is_exhausted("c", "U-X") is False
        await _seed_usage("U-X", "c", 99, 0)
        assert await is_exhausted("c", "U-X") is False
        await _seed_usage("U-X", "c", 1, 0)  # 100 = limit → 触发
        assert await is_exhausted("c", "U-X") is True
