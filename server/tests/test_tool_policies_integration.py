"""客服代查 API 用 DB 中的 tool_policies 决定放行/脱敏；表空走默认。"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def env(seeded_db, monkeypatch):
    monkeypatch.setenv("STAFF_JWT_SECRET", "test")
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.auth.staff_session import issue_staff_token
    from ai_engine.persistence import db, tool_policies
    from ai_engine.persistence.staff import create_staff

    tool_policies.invalidate_cache()

    await create_staff("SE1", "高级", "senior", "x")
    await db.execute(
        "INSERT INTO conversations(id, user_type, subject_id, mode, created_at) "
        "VALUES (10, 'b', 'BU1', 'human_takeover', '2026-05-30 00:00:00')"
    )
    yield {"se": issue_staff_token("SE1", "senior")}
    tool_policies.invalidate_cache()
    monkeypatch.undo()
    settings.reload()


def _h(t):
    return {"Authorization": f"Bearer {t}"}


async def test_default_whitelist_allows_query_user(env):
    """表空时 senior 调 query_user 不会被白名单 403（具体执行可能因业务库未配返回别的错，
    本测试只要求"非 403 因白名单失败"——即必须越过白名单这一关）。"""
    from ai_engine import main as main_mod

    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post(
            "/staff/api/v1/conversations/10/ai-tools/query_user",
            json={"params": {"user_id": "u1"}},
            headers=_h(env["se"]),
        )
    # 任何非 400 / 非 "tool not allowed" 都算通过白名单；具体业务结果不重要
    assert not (r.status_code == 400 and "tool not allowed" in r.text)


async def test_db_override_denies_query_user_for_senior(env):
    """DB 中显式禁用 query_user/senior 后，senior 代查该工具应 403。"""
    from ai_engine import main as main_mod
    from ai_engine.persistence import tool_policies

    await tool_policies.upsert_many(
        "AD1",
        [
            {
                "tool_name": "query_user",
                "role": "senior",
                "allowed": 0,
                "unmask_allowed": 0,
            }
        ],
    )
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://t") as c:
        r = await c.post(
            "/staff/api/v1/conversations/10/ai-tools/query_user",
            json={"params": {"user_id": "u1"}},
            headers=_h(env["se"]),
        )
    assert r.status_code == 400
    assert "tool not allowed" in r.text
