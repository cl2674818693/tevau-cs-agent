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


async def test_staff_log_endpoints_require_auth(staff_token):
    from ai_engine import main as main_mod

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/staff/api/v1/audits/recent")  # 无 token
    assert r.status_code == 401


async def test_conversation_messages_audits_feedback(staff_token):
    from ai_engine import main as main_mod
    from ai_engine.persistence import audit as audit_dao
    from ai_engine.persistence import conversations as c
    from ai_engine.persistence import feedback as fb

    cid = await c.create_conversation(user_type="c", subject_id="U1")
    tid = await c.append_user_turn(cid, "范围外问题", "cm-x")
    await c.set_turn_verdict(tid, "no")
    await c.finalize_turn(tid, "failed", "INTERNAL_ERROR")
    mid = await c.append_message(cid, "assistant", "答复")
    await fb.add_feedback(cid, mid, "down", "不准", "U1", "c")
    await audit_dao.log_tool_call(cid, "query_user", {"x": 1}, 0, 5, True, "越权被拒")

    transport = ASGITransport(app=main_mod.app)
    headers = {"Authorization": f"Bearer {staff_token}"}
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        msgs = (
            await client.get(f"/staff/api/v1/conversations/{cid}/messages", headers=headers)
        ).json()
        audits = (
            await client.get(f"/staff/api/v1/conversations/{cid}/tool-audits", headers=headers)
        ).json()
        fbk = (
            await client.get(f"/staff/api/v1/conversations/{cid}/feedback", headers=headers)
        ).json()
        recent = (
            await client.get("/staff/api/v1/audits/recent?rejected=true", headers=headers)
        ).json()

    turn = next(m for m in msgs["messages"] if m["id"] == tid)
    assert turn["status"] == "failed" and turn["topic_verdict"] == "no"
    assert audits["audits"][0]["tool_name"] == "query_user"
    assert audits["audits"][0]["rejected"] == 1
    assert fbk["feedback"][0]["rating"] == "down"
    assert recent["audits"][0]["reject_reason"] == "越权被拒"
