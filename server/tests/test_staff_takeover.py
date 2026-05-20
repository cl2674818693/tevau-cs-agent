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


async def test_take_and_release(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "human_pending")

    transport = ASGITransport(app=main_mod.app)
    headers = {"Authorization": f"Bearer {staff_token}"}
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=headers)
        assert r.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "human_takeover" and sid == "S100"

        r2 = await client.post(f"/staff/api/v1/conversations/{cid}/take", headers=headers)
        assert r2.status_code == 409  # 已被接管，原子拒绝

        r3 = await client.post(f"/staff/api/v1/conversations/{cid}/release", headers=headers)
        assert r3.status_code == 200
        mode, sid = await get_mode(cid)
        assert mode == "ai" and sid is None


async def test_send_message(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, list_messages, set_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "human_takeover", "S100")

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "您好，您的卡片已为您解锁。"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert r.status_code == 200

    msgs = await list_messages(cid)
    assert any(m["role"] == "human_agent" and "解锁" in m["content"] for m in msgs)


async def test_send_message_not_your_conversation(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence.conversations import create_conversation, set_mode

    cid = await create_conversation(user_type="c", subject_id="U1")
    await set_mode(cid, "human_takeover", "OTHER_STAFF")  # 别人接管的

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/staff/api/v1/conversations/{cid}/messages",
            json={"content": "x"},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
    assert r.status_code == 403


async def test_staff_endpoints_require_token():
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/staff/api/v1/conversations")
    assert r.status_code == 401
