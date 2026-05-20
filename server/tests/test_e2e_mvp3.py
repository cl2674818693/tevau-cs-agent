"""MVP-3 端到端验收：事项中心 + self-check + 治理 + 客服 C 方案 + 可观测。"""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _resp(text: str, stop: str = "end_turn") -> MagicMock:
    return MagicMock(
        content=[MagicMock(type="text", text=text)],
        stop_reason=stop,
        usage=MagicMock(input_tokens=1, output_tokens=1),
    )


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "e2e")
    monkeypatch.setenv("EVENT_CENTER_SECRET_CURRENT", "cur-key")
    monkeypatch.setenv("EVENT_CENTER_SECRET_PREVIOUS", "old-key")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("EN1", "工程师", "engineer", "x")
    return {
        "agent": issue_staff_token("AG1", "agent"),
        "eng": issue_staff_token("EN1", "engineer"),
    }


def _bh() -> dict[str, str]:
    return {"X-BU-ID": "BU00243780"}


def _sh(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_scenario1_ticket_callback_reaches_dialog_bus(env):
    """剧本1：建工单 → assigned 回调 → 会话总线收到状态变更。"""
    from ai_engine import main as main_mod
    from ai_engine.api import staff_conversations as sc
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.tickets import create_ticket

    cid = await create_conversation("b", "BU00243780")
    await create_ticket(external_id="AI-E2E", conversation_id=cid, payload={"category": "bug"})
    q = sc.register_subscriber(cid)

    raw = json.dumps({"event": "assigned", "actor": "ops"}).encode()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-E2E/events",
            content=raw,
            headers={"X-Signature": _sign(raw, "cur-key"), "Content-Type": "application/json"},
        )
    assert r.status_code == 200
    ev = q.get_nowait()
    sc.unregister_subscriber(cid, q)
    assert ev["type"] == "assigned" and ev["external_id"] == "AI-E2E"


async def test_scenario2_previous_hmac_key_still_valid(env):
    """剧本2：双 key 轮换 —— PREVIOUS key 签名仍通过。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation
    from ai_engine.persistence.tickets import create_ticket

    cid = await create_conversation("b", "BU00243780")
    await create_ticket(external_id="AI-OLD", conversation_id=cid, payload={"category": "bug"})

    raw = json.dumps({"event": "in_progress", "actor": "ops"}).encode()
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/api/v1/tickets/AI-OLD/events",
            content=raw,
            headers={"X-Signature": _sign(raw, "old-key"), "Content-Type": "application/json"},
        )
    assert r.status_code == 200


async def test_scenario3_self_check_revision_reaches_user(env, monkeypatch):
    """剧本3：self-check 把草稿改写后再流给用户。"""
    from ai_engine.agent import runtime
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    seq = iter([_resp("草稿：随便看看"), _resp("修订：去看 card_bind.py:120，证据 X")])
    fake = MagicMock()
    fake.messages.create = AsyncMock(side_effect=lambda **kw: next(seq))
    monkeypatch.setattr(ac, "_client", fake)

    texts = []
    async for ev in runtime.run_turn(
        conversation_id=cid, user_type="b", subject_id="BU00243780", user_message="问"
    ):
        if ev["type"] == "text":
            texts.append(ev["text"])
    joined = "".join(texts)
    assert "草稿" not in joined and "修订" in joined


async def test_scenario4_token_budget_refusal(env, monkeypatch):
    """剧本4：token 超额 → 下次 chat 拿到额度用完系统消息。"""
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "1")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    fake = MagicMock()
    fake.messages.create = AsyncMock(return_value=_resp("回复"))
    monkeypatch.setattr(ac, "_client", fake)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        # 第一次：正常（记账 2 tokens）
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=一", headers=_bh()
        ) as r1:
            async for _ in r1.aiter_lines():
                pass
        # 第二次：超额拒服
        body = []
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=二", headers=_bh()
        ) as r2:
            async for line in r2.aiter_lines():
                body.append(line)
    assert "额度已用完" in "\n".join(body)


async def test_scenario5_ai_draft_review_flow(env, monkeypatch):
    """剧本5：ai_draft → 用户问 → 落草稿 → approve 后才有 assistant 消息。"""
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import create_conversation, list_messages, set_mode

    cid = await create_conversation("b", "BU00243780")
    await set_mode(cid, "ai_draft", "AG1")
    fake = MagicMock()
    fake.messages.create = AsyncMock(return_value=_resp("AI 草稿答复"))
    monkeypatch.setattr(ac, "_client", fake)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        async with client.stream(
            "GET", f"/api/v1/chat?conversation_id={cid}&message=问", headers=_bh()
        ) as r:
            joined = "\n".join([ln async for ln in r.aiter_lines()])
        assert "review" in joined
        assert "AI 草稿答复" not in joined  # 未流给用户
        # approve
        ra = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve", headers=_sh(env["agent"])
        )
        assert ra.status_code == 200
    msgs = await list_messages(cid)
    assert any(m["role"] == "assistant" and "草稿答复" in m["content"] for m in msgs)


async def test_scenario6_transfer_to_engineer(env):
    """剧本6：agent 接管 → 转 engineer → engineer 成为受理人。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, get_mode

    cid = await create_conversation("b", "BU00243780")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=_sh(env["agent"]))
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/transfer-to/EN1", headers=_sh(env["agent"])
        )
        assert r.status_code == 200
    mode, sid = await get_mode(cid)
    assert mode == "human_takeover" and sid == "EN1"


async def test_scenario7_metrics_exposed(env):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/metrics")
    assert r.status_code == 200
    # active_conversations 是 Gauge 始终存在；llm_calls 在前面剧本已触发
    for name in ("ai_engine_active_conversations", "ai_engine_llm_calls_total"):
        assert name in r.text
