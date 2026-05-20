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
    return {
        "agent": issue_staff_token("AG1", "agent"),
        "senior": issue_staff_token("SR1", "senior"),
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
