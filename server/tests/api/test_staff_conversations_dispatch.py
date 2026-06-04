"""Task 8: list/take 加 :me 过滤（隔离别人未到期的派单）。

被测逻辑：
- take：WHERE assigned_staff_id IS NULL OR assigned_staff_id=:sub
  → 派单已分配给我时可接管；分配给别人时 409。
- list human_pending：只返回开放池（assigned_staff_id IS NULL）或派给我的会话，
  隔离派给别人的会话。
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ai_engine.api.staff_conversations import router as staff_conv_router
from ai_engine.auth.staff_session import issue_staff_token
from ai_engine.persistence import db
from ai_engine.persistence.db import init_db
from ai_engine.persistence.schema import now_str
from ai_engine import persistence
from ai_engine.persistence import conversations as conv_dao


# ── 夹具 ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(staff_conv_router)
    return a


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def init_self_db(temp_db_url: str, monkeypatch) -> AsyncIterator[str]:
    monkeypatch.setenv("STAFF_JWT_SECRET", "test-staff-secret")
    from ai_engine.config import settings

    settings.reload()
    await init_db()
    yield temp_db_url
    from ai_engine.persistence import db as db_mod

    eng = db_mod._engines.pop(temp_db_url, None)
    if eng is not None:
        await eng.dispose()
    settings.reload()


def _agent_token(sub: str) -> str:
    return issue_staff_token(sub, "agent")


def _headers(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_agent_token(sub)}"}


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_take_succeeds_when_assigned_to_me(
    init_self_db, client: AsyncClient
) -> None:
    sid = "A"
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await db.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id=:s, assigned_at=:t "
        "WHERE id=:c",
        {"s": sid, "t": now_str(), "c": cid},
    )
    r = await client.post(
        f"/staff/api/v1/conversations/{cid}/take",
        headers=_headers(sid),
    )
    assert r.status_code == 200
    row = await db.fetch_one("SELECT mode FROM conversations WHERE id=:c", {"c": cid})
    assert row["mode"] == "human_takeover"


@pytest.mark.asyncio
async def test_take_fails_when_assigned_to_other(
    init_self_db, client: AsyncClient
) -> None:
    cid = await conv_dao.create_conversation(user_type="c", subject_id="u")
    await db.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id='B', assigned_at=:t "
        "WHERE id=:c",
        {"t": now_str(), "c": cid},
    )
    r = await client.post(
        f"/staff/api/v1/conversations/{cid}/take",
        headers=_headers("A"),
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_human_pending_filters_other_staff_assignments(
    init_self_db, client: AsyncClient
) -> None:
    c_a = await conv_dao.create_conversation(user_type="c", subject_id="u1")
    c_b = await conv_dao.create_conversation(user_type="c", subject_id="u2")
    c_open = await conv_dao.create_conversation(user_type="c", subject_id="u3")
    await db.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id='A', assigned_at=:t "
        "WHERE id=:c",
        {"t": now_str(), "c": c_a},
    )
    await db.execute(
        "UPDATE conversations SET mode='human_pending', assigned_staff_id='B', assigned_at=:t "
        "WHERE id=:c",
        {"t": now_str(), "c": c_b},
    )
    await db.execute(
        "UPDATE conversations SET mode='human_pending' WHERE id=:c",
        {"c": c_open},
    )

    r = await client.get(
        "/staff/api/v1/conversations?status=human_pending",
        headers=_headers("A"),
    )
    assert r.status_code == 200
    ids = [row["id"] for row in r.json()]
    assert c_a in ids
    assert c_open in ids
    assert c_b not in ids
