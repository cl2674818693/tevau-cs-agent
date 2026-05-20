from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def staff_token(temp_db_url, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.staff import create_staff

    await init_db()
    await create_staff("S100", "张三", "agent", "x")
    return issue_staff_token("S100", "agent")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_enable_disable(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, get_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/enable", headers=_headers(staff_token)
        )
        assert r.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "ai_draft" and sid == "S100"

        r2 = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/disable", headers=_headers(staff_token)
        )
        assert r2.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "ai" and sid is None


async def test_approve_sends_draft_as_assistant(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import (
        create_conversation,
        list_messages,
        save_ai_draft,
        set_mode,
    )

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "ai_draft", "S100")
    await save_ai_draft(cid, "这是 AI 草稿回答。")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve", headers=_headers(staff_token)
        )
        assert r.status_code == 200

    msgs = await list_messages(cid)
    assert any(m["role"] == "assistant" and "草稿" in m["content"] for m in msgs)
    assert not any(m["role"] == "ai_draft" for m in msgs)  # 草稿已清


async def test_reject_sends_rewrite_as_human(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import (
        create_conversation,
        list_messages,
        save_ai_draft,
        set_mode,
    )

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "ai_draft", "S100")
    await save_ai_draft(cid, "AI 原草稿")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/reject",
            json={"rewrite": "客服改写后的答复"},
            headers=_headers(staff_token),
        )
        assert r.status_code == 200

    msgs = await list_messages(cid)
    assert any(m["role"] == "human_agent" and "改写" in m["content"] for m in msgs)
    assert not any(m["role"] == "ai_draft" for m in msgs)


async def test_approve_not_your_conversation(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, save_ai_draft, set_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "ai_draft", "OTHER")
    await save_ai_draft(cid, "x")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/ai-draft/approve", headers=_headers(staff_token)
        )
    assert r.status_code == 403


async def test_chat_in_ai_draft_mode_does_not_stream_to_user(seeded_db, monkeypatch):
    """ai_draft 模式：chat 不把 AI 文本流给用户，只提示 review 并落草稿。"""
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine import main as main_mod
    from ai_engine.integrations import anthropic_client as ac
    from ai_engine.persistence.conversations import (
        create_conversation,
        get_latest_ai_draft,
        set_mode,
    )

    cid = await create_conversation(user_type="b", subject_id="BU00243780")
    await set_mode(cid, "ai_draft", "S100")

    fake = MagicMock()
    fake.messages.create = AsyncMock(
        side_effect=[
            MagicMock(
                content=[MagicMock(type="text", text="AI 想说的回答")],
                stop_reason="end_turn",
                usage=MagicMock(input_tokens=1, output_tokens=1),
            ),
            MagicMock(
                content=[MagicMock(type="text", text="AI 想说的回答")],
                stop_reason="end_turn",
                usage=MagicMock(input_tokens=1, output_tokens=1),
            ),
        ]
    )
    monkeypatch.setattr(ac, "_client", fake)

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        body = []
        async with client.stream(
            "GET",
            f"/api/v1/chat?conversation_id={cid}&message=问题",
            headers={"X-BU-ID": "BU00243780"},
        ) as resp:
            async for line in resp.aiter_lines():
                body.append(line)
    joined = "\n".join(body)
    assert "review" in joined
    assert "AI 想说的回答" not in joined  # 草稿没流给用户
    # 草稿已落库
    assert (await get_latest_ai_draft(cid)) == "AI 想说的回答"
