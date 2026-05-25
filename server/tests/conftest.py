import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest


class _FakeMessageStream:
    """模拟 anthropic AsyncMessageStreamManager：async with 进入后 text_stream 流文本增量，
    get_final_message 返回完整消息。配合 runtime 的 _ac.stream_turn 使用。
    """

    def __init__(self, resp: object) -> None:
        self._resp = resp

    async def __aenter__(self) -> "_FakeMessageStream":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def _resolve(self) -> object:
        import inspect

        if inspect.iscoroutine(self._resp):  # responder 为 async def 时返回 coroutine
            self._resp = await self._resp
        return self._resp

    @property
    def text_stream(self):  # type: ignore[no-untyped-def]
        async def _gen():  # type: ignore[no-untyped-def]
            resp = await self._resolve()
            for b in getattr(resp, "content", []):
                if getattr(b, "type", None) == "text":
                    yield getattr(b, "text", "")

        return _gen()

    async def get_final_message(self) -> object:
        return await self._resolve()


def make_fake_stream(responder: object) -> MagicMock:
    """构造 _client.messages.stream 的替身。

    responder 可为：单个 resp、resp 序列（每次调用取下一个）、或 callable(**kwargs)->resp。
    返回 MagicMock（可断言 call_count / call_args_list），调用即返回 _FakeMessageStream。
    """
    import inspect

    # 注意：MagicMock resp 本身可调用，不能用 callable() 判断；仅真正的函数/方法才当响应器。
    if inspect.isroutine(responder):
        fn = responder
    elif isinstance(responder, (list, tuple)):
        seq = iter(responder)
        fn = lambda **kw: next(seq)  # noqa: E731  逐轮取下一个 resp
    else:
        fn = lambda **kw: responder  # noqa: E731  单个 resp：每轮复用（等价 return_value）

    def _stream(**kwargs: object) -> _FakeMessageStream:
        return _FakeMessageStream(fn(**kwargs))

    return MagicMock(side_effect=_stream)


@pytest.fixture
def fake_stream():
    """便捷夹具：返回 make_fake_stream，用于把 _client.messages.stream 替换成假流。"""
    return make_fake_stream


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

    # nexus 也指向同一测试库（bu_login 校验 t_nexus_company_info）
    await business_db.init_business_dbs(mysql_url, mysql_url)
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
