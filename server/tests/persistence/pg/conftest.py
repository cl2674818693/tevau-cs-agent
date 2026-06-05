"""B-P0-6: Postgres 集成测试 fixture（testcontainers）。

为什么需要：自有库测试默认跑 SQLite，但生产用 Postgres asyncpg。两者在以下方面行为
差异显著：
- `CAST(:p AS TEXT) IS NULL` 在 PG 严格类型检查下可能因绑定类型不匹配抛错；
- ON CONFLICT 语法（SQLite 3.24+/PG 都支持，但行为细节有差异）；
- NULL 比较语义（PG `=` 严格三值，SQLite 部分场景宽松）；
- 字符串拼接 `||` / 时间戳精度（PG 微秒 vs SQLite 秒）。

本 conftest 起一个会话级 PostgresContainer，无 docker 时 skip 整个 pg/ 目录。
镜像测试通过 `--db sqlite,postgres` 参数化或独立 `test_*_pg.py` 文件覆盖关键 DAO。
"""

import asyncio
import subprocess
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest


def _docker_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=8)  # noqa: S607
        return r.returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def pg_container_url() -> str:
    """会话级 PostgreSQL 容器；无 docker 时 skip。返回 asyncpg+postgresql URL。"""
    if not _docker_ok():
        pytest.skip("docker not available")
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    try:
        raw = container.get_connection_url()
        # testcontainers 默认 postgresql+psycopg2:// → 改成 asyncpg
        parsed = urlparse(raw)
        url = (
            f"postgresql+asyncpg://{parsed.username}:{parsed.password}"
            f"@{parsed.hostname}:{parsed.port}{parsed.path}"
        )
        yield url
    finally:
        container.stop()


@pytest.fixture
async def pg_db(monkeypatch, pg_container_url) -> AsyncIterator[str]:
    """每个测试用例独立 schema：drop public + 重建后初始化表。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DB_URL", pg_container_url)
    from ai_engine.config import settings
    from ai_engine.persistence import db as db_mod
    from ai_engine.persistence.db import get_conn, init_db
    from sqlalchemy import text

    settings.reload()
    async with get_conn() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await init_db()
    yield pg_container_url
    # cleanup engine cache so 下个 case fresh init
    eng = db_mod._engines.pop(pg_container_url, None)
    if eng is not None:
        await eng.dispose()
