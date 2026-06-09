"""MySQL 集成测试 fixture（testcontainers）。

为什么需要：自有库测试默认跑 SQLite（建表快、ON CONFLICT 等语法一致），但生产用
MySQL aiomysql。两者在以下方面行为差异：
- ON CONFLICT vs ON DUPLICATE KEY UPDATE（已在 4 处 upsert 用 db.dialect_name() 分发）；
- INSERT 拿自增 id：MySQL 走 cursor.lastrowid（不支持 RETURNING）；
- 字符串大小写比较（默认 utf8mb4_unicode_ci 不区分大小写，SQLite 默认 BINARY 区分）；
- NULL 比较 / `CAST(:p AS TEXT)` 类型推导差异。

本 conftest 起一个会话级 MySqlContainer，无 docker 时 skip 整个 mysql/ 目录。
"""

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
def mysql_container_url() -> str:
    """会话级 MySQL 容器；无 docker 时 skip。返回 aiomysql+mysql URL。"""
    if not _docker_ok():
        pytest.skip("docker not available")
    from testcontainers.mysql import MySqlContainer

    container = MySqlContainer("mysql:8.0", username="ai", password="ai_test_pw", dbname="ai_engine")
    container.start()
    try:
        raw = container.get_connection_url()
        # testcontainers 默认 mysql+pymysql:// → 改成 aiomysql
        parsed = urlparse(raw)
        url = (
            f"mysql+aiomysql://{parsed.username}:{parsed.password}"
            f"@{parsed.hostname}:{parsed.port}{parsed.path}"
        )
        yield url
    finally:
        container.stop()


@pytest.fixture
async def mysql_db(monkeypatch, mysql_container_url) -> AsyncIterator[str]:
    """每个测试用例独立库状态：drop 所有表后重建（init_db = metadata.create_all）。

    不在 teardown 主动 dispose engine——pytest-asyncio 跨用例切 event loop 时
    aiomysql 关闭连接会触发 RuntimeError("Event loop is closed")。engine 按 URL
    缓存，跨用例复用同一个，进程退出时自然 GC，无 leak 风险（测试场景下）。
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DB_URL", mysql_container_url)

    from ai_engine.config import settings
    from ai_engine.persistence import db as db_mod
    from ai_engine.persistence.db import _engine, init_db
    from ai_engine.persistence.schema import metadata

    # 每个 test 进入时清掉 engine cache：不主动 dispose（aiomysql 跨 event loop close 会
    # 触发 "Event loop is closed"），让旧 engine 由 GC 处理；本 test 用全新 engine 绑定到
    # 当前 event loop，避免连接复用到已关闭的 loop。
    db_mod._engines.pop(mysql_container_url, None)

    settings.reload()
    async with _engine().begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await init_db()
    yield mysql_container_url
