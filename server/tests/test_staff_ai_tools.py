import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def tokens(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.staff import create_staff

    await create_staff("AG1", "客服", "agent", "x")
    await create_staff("SR1", "高级", "senior", "x")
    await create_staff("EN1", "工程师", "engineer", "x")
    return {
        "agent": issue_staff_token("AG1", "agent"),
        "senior": issue_staff_token("SR1", "senior"),
        "eng": issue_staff_token("EN1", "engineer"),
    }


def _h(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def test_agent_cannot_run_ai_tools(tokens):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {}},
            headers=_h(tokens["agent"]),
        )
    assert r.status_code == 403


async def test_tool_not_in_whitelist_rejected(tokens):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/create_ticket",
            json={"params": {}},
            headers=_h(tokens["senior"]),
        )
    assert r.status_code == 400


async def test_senior_runs_tool_with_forced_identity(tokens, monkeypatch):
    """senior 代查：subject_id 被强制为会话身份，AI 传的别的 bu_id 被覆盖。"""
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import base
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")

    seen: dict[str, object] = {}

    async def fake_handler(**kwargs):
        seen.update(kwargs)
        return {"masked_phone": "138****78"}

    tool = base.get("query_user")
    assert tool is not None
    monkeypatch.setattr(tool, "handler", fake_handler)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {"bu_id": "BU_OTHER", "user_id": "U1"}},
            headers=_h(tokens["senior"]),
        )
    assert r.status_code == 200
    out = r.json()
    assert out["ok"] is True
    assert out["data"]["masked_phone"] == "138****78"
    # 身份被强制覆盖为会话 bu
    assert seen["bu_id"] == "BU00243780"


async def test_unknown_conversation_404(tokens):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            "/staff/api/v1/conversations/999999/ai-tools/query_user",
            json={"params": {}},
            headers=_h(tokens["senior"]),
        )
    assert r.status_code == 404


async def test_engineer_unmask_true_senior_false(tokens, monkeypatch):
    """spec §13.3：engineer 代查解锁脱敏（handler 收到 unmask=True），senior 不解锁。"""
    from ai_engine import main as main_mod
    from ai_engine.agent.tools import base
    from ai_engine.persistence.conversations import create_conversation

    cid = await create_conversation("b", "BU00243780")

    seen: dict[str, object] = {}

    async def fake_handler(**kwargs):
        seen["unmask"] = kwargs.get("unmask", False)
        return {"ok": True}

    tool = base.get("query_user")
    assert tool is not None
    monkeypatch.setattr(tool, "handler", fake_handler)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {"user_id": "U1"}},
            headers=_h(tokens["eng"]),
        )
        assert seen["unmask"] is True

        await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-tools/query_user",
            json={"params": {"user_id": "U1"}},
            headers=_h(tokens["senior"]),
        )
        assert seen["unmask"] is False


async def test_ai_cannot_self_unlock_unmask(seeded_db):
    """AI 走 dispatch 时即便 params 带 unmask=True 也被剥离（不能自助解锁）。"""
    from ai_engine.agent.tool_router import dispatch
    from ai_engine.agent.tools import base
    from ai_engine.persistence.db import init_db

    await init_db()
    seen: dict[str, object] = {}

    async def fake_handler(**kwargs):
        seen["unmask"] = kwargs.get("unmask", False)
        return {"ok": True}

    tool = base.get("query_card")
    assert tool is not None
    import unittest.mock as m

    with m.patch.object(tool, "handler", fake_handler):
        # 模拟 AI 自带 unmask=True，dispatch 未传 unmask（默认 False）
        await dispatch(
            tool_name="query_card",
            params={"card_id": "C1", "unmask": True},
            user_type="b",
            subject_id="BU1",
            conversation_id=1,
        )
    assert seen["unmask"] is False
