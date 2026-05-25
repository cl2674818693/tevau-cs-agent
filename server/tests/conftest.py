import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pytest


@pytest.fixture(autouse=True)
def _security_test_env(monkeypatch):
    """测试环境：开启 X-BU-ID 信任（多数测试用它模拟 B 端身份）+ 配置 B 端 session 签名密钥。"""
    monkeypatch.setenv("DEV_TRUST_BU_HEADER", "true")
    monkeypatch.setenv("BU_SESSION_SECRET", "test-bu-secret")
    from ai_engine.config import settings

    settings.reload()
    yield


def _docker_ok() -> bool:
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=8)  # noqa: S607
        return r.returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def mysql_url():
    """会话级 MySQL 容器（testcontainers），加载 unlimitpay_seed.sql。无 docker 时 skip。"""
    if not _docker_ok():
        pytest.skip("docker not available")
    from testcontainers.mysql import MySqlContainer

    with MySqlContainer("mysql:8.0") as mysql:
        raw = mysql.get_connection_url().replace("mysql+pymysql://", "mysql://")
        import pymysql

        p = urlparse(raw)
        conn = pymysql.connect(
            host=p.hostname,
            port=p.port or 3306,
            user=p.username,
            password=p.password,
            database=(p.path or "").lstrip("/"),
        )
        try:
            seed = Path("tests/fixtures/unlimitpay_seed.sql").read_text(encoding="utf-8")
            with conn.cursor() as cur:
                for stmt in seed.split(";"):
                    if stmt.strip():
                        cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        yield raw


@pytest.fixture
async def business_mysql(monkeypatch, mysql_url):
    """把 business_db 指向测试 MySQL 容器并初始化连接池。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("UNLIMITPAY_DB_URL", mysql_url)
    from ai_engine.config import settings

    settings.reload()
    from ai_engine.persistence import business_db

    await business_db.init_business_dbs(mysql_url, None)
    yield mysql_url
    await business_db.close_all()


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

    from sqlalchemy import text

    from ai_engine.persistence.db import get_conn, init_db

    await init_db()
    sql = Path("tests/fixtures/seed.sql").read_text(encoding="utf-8")  # noqa: ASYNC240  测试 setup 读小文件
    async with get_conn() as conn:
        for stmt in sql.split(";"):
            if stmt.strip():
                await conn.execute(text(stmt))
    return temp_db_url
