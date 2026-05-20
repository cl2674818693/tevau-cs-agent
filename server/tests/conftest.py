import os
import tempfile

import pytest


@pytest.fixture
def temp_db_url(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DB_URL", url)
    from ai_engine.config import settings

    settings.reload()
    yield url
    os.remove(path)


@pytest.fixture
async def seeded_db(temp_db_url):
    from pathlib import Path

    from ai_engine.persistence.db import get_conn, init_db

    await init_db()
    sql = Path("tests/fixtures/seed.sql").read_text(encoding="utf-8")  # noqa: ASYNC240  测试 setup 读小文件
    async with get_conn() as conn:
        await conn.executescript(sql)
        await conn.commit()
    return temp_db_url
