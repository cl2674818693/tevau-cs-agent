"""PG6: 真 Postgres 冒烟测试。

证明整套 persistence 在真实 Postgres 上跑通：create_all 建表、RETURNING id、命名参数、
ON CONFLICT upsert（token_budget）、时间窗口查询（find_open_ticket）。无 docker 时跳过。
"""

import subprocess

import pytest


def _docker_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=8)  # noqa: S607
        return r.returncode == 0
    except Exception:
        return False


@pytest.fixture
async def pg_db(monkeypatch):
    if not _docker_ok():
        pytest.skip("docker not available")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        # 转成 asyncpg async URL（容器默认给 psycopg2 串）
        url = pg.get_connection_url().replace("+psycopg2", "+asyncpg")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("DB_URL", url)
        from ai_engine.config import settings

        settings.reload()
        from ai_engine.persistence.db import _engines, init_db

        await init_db()
        yield url
        eng = _engines.pop(url, None)
        if eng is not None:
            await eng.dispose()


async def test_full_crud_on_real_postgres(pg_db):
    from ai_engine.governance.token_budget import check_and_record
    from ai_engine.persistence.conversations import (
        append_message,
        create_conversation,
        get_conversation,
        list_messages,
    )
    from ai_engine.persistence.staff import authenticate, create_staff
    from ai_engine.persistence.tickets import (
        append_ticket_event,
        create_ticket,
        find_open_ticket_for_subject,
        get_ticket,
    )

    # 会话 + 消息（RETURNING id、命名参数、自增主键）
    cid = await create_conversation(user_type="b", subject_id="BU1")
    assert isinstance(cid, int) and cid > 0
    await append_message(cid, role="user", content="hi")
    await append_message(cid, role="assistant", content="hello")
    conv = await get_conversation(cid)
    assert conv is not None and conv["subject_id"] == "BU1"
    assert [m["role"] for m in await list_messages(cid)] == ["user", "assistant"]

    # 工单 + 事件 + 时间窗口查询
    await create_ticket("T-1", cid, {"bu_id": "BU1", "user_type": "b", "severity": "p2"})
    await append_ticket_event("T-1", "assigned", actor="a", comment="ok")
    t = await get_ticket("T-1")
    assert t is not None and t["events"][-1]["event"] == "assigned"
    assert await find_open_ticket_for_subject("BU1", "b") == "T-1"

    # token 计量 ON CONFLICT upsert（累加）
    ok1, _ = await check_and_record("b", "BU1", 100, 50)
    ok2, info = await check_and_record("b", "BU1", 10, 5)
    assert ok1 and ok2 and info["used"] == 165

    # 客服建号 + 认证（CHECK 约束 role）
    await create_staff("S1", "Agent", "agent", "pw123456")
    assert (await authenticate("S1", "pw123456")) is not None
    assert (await authenticate("S1", "wrong")) is None
