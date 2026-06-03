"""Persistence: business_db.py — 业务只读库连接（MySQL via testcontainers）。

策略：使用 `business_mysql` fixture（需 docker，无则 skip）。覆盖：
- parse_mysql_url（纯函数）
- BusinessDB.fetch_one / fetch_all（参数化查询 + 编码 utf8mb4）
- BusinessDB.fetch_all limit
- get_db 名注册 + close
- init_business_dbs 仅初始化非空 url
"""

import pytest

from ai_engine.persistence import business_db


class TestParseMysqlUrl:
    """纯函数：URL → 连接参数。无需 docker。"""

    def test_full_url(self) -> None:
        cfg = business_db.parse_mysql_url("mysql://user:pw@host.example:3307/dbname")
        assert cfg == {
            "user": "user",
            "password": "pw",
            "host": "host.example",
            "port": 3307,
            "db": "dbname",
        }

    def test_default_port(self) -> None:
        cfg = business_db.parse_mysql_url("mysql://user:pw@host/db")
        assert cfg["port"] == 3306

    def test_invalid_scheme_raises(self) -> None:
        with pytest.raises(ValueError):
            business_db.parse_mysql_url("postgres://x")

    def test_empty_db_path(self) -> None:
        cfg = business_db.parse_mysql_url("mysql://user:pw@host:3306")
        assert cfg["db"] == ""


class TestGetDb:
    def test_uninitialized_raises(self) -> None:
        # 清掉状态防止其他测试串扰
        business_db._pools.clear()
        with pytest.raises(RuntimeError, match="not initialized"):
            business_db.get_db("unlimitpay")


class TestBusinessDBQueries:
    """需 docker。无 docker 时 business_mysql fixture 内部 skip。"""

    async def test_fetch_one(self, business_mysql) -> None:
        db = business_db.get_db("unlimitpay")
        row = await db.fetch_one("SELECT user_id, email FROM user WHERE user_id=%s", ("U1",))
        assert row is not None
        assert row["user_id"] == "U1"
        assert row["email"] == "alice@x.com"

    async def test_fetch_one_missing(self, business_mysql) -> None:
        db = business_db.get_db("unlimitpay")
        row = await db.fetch_one(
            "SELECT user_id FROM user WHERE user_id=%s", ("NOPE",)
        )
        assert row is None

    async def test_fetch_all_default_limit(self, business_mysql) -> None:
        db = business_db.get_db("unlimitpay")
        rows = await db.fetch_all("SELECT user_id FROM user")
        ids = {r["user_id"] for r in rows}
        assert "U1" in ids and "U2" in ids

    async def test_fetch_all_limit(self, business_mysql) -> None:
        db = business_db.get_db("unlimitpay")
        rows = await db.fetch_all("SELECT user_id FROM user", limit=1)
        assert len(rows) == 1

    async def test_chinese_field_utf8mb4(self, business_mysql) -> None:
        """charset=utf8mb4 否则 lock_reason 中文乱码。"""
        db = business_db.get_db("unlimitpay")
        row = await db.fetch_one(
            "SELECT lock_reason FROM card WHERE card_id=%s", ("C100",)
        )
        assert row is not None
        assert "风控" in row["lock_reason"]

    async def test_parameterized_query_prevents_injection(self, business_mysql) -> None:
        db = business_db.get_db("unlimitpay")
        # 注入串作为参数：不应触发 SQL 错误，应当返回空
        rows = await db.fetch_all(
            "SELECT user_id FROM user WHERE user_id=%s", ("U1' OR '1'='1",)
        )
        assert rows == []

    async def test_get_db_returns_same_instance(self, business_mysql) -> None:
        a = business_db.get_db("unlimitpay")
        b = business_db.get_db("unlimitpay")
        assert a is b

    async def test_nexus_pool_initialized(self, business_mysql) -> None:
        """business_mysql fixture 同时把 nexus 指向同一个测试 MySQL。"""
        db = business_db.get_db("nexus")
        # 这是同一 schema，能查 t_nexus_company_info
        row = await db.fetch_one(
            "SELECT tenant_id, company_name FROM t_nexus_company_info WHERE tenant_id=%s",
            ("1011010000068",),
        )
        assert row is not None
        assert row["tenant_id"] == "1011010000068"


class TestInitAndClose:
    """init_business_dbs 接受 None 时跳过；close_all 释放并清空。"""

    async def test_init_with_none_skips(self) -> None:
        business_db._pools.clear()
        await business_db.init_business_dbs(None, None)
        assert business_db._pools == {}
        # 再 close_all 不抛错
        await business_db.close_all()

    async def test_close_all_clears(self, business_mysql) -> None:
        assert "unlimitpay" in business_db._pools
        await business_db.close_all()
        assert business_db._pools == {}
        with pytest.raises(RuntimeError):
            business_db.get_db("unlimitpay")


class TestExecWithRetry:
    """_exec_with_retry：ping 失败/OperationalError(2013/2006/2003) 重试一次，
    其它异常直接抛；fix 阿里云 RDS pool idle 后 stale connection 击穿。"""

    async def _make_fake_pool(self, conns):
        """conns: list of fake conn objects, pool.acquire() 按序返回。"""
        from unittest.mock import AsyncMock, MagicMock
        pool = MagicMock()
        acquire_iter = iter(conns)
        pool.acquire = AsyncMock(side_effect=lambda: next(acquire_iter))
        pool.release = MagicMock()
        return pool

    async def _make_fake_conn(self, *, ping_ok=True, exec_err=None, fetchone_result=None):
        from unittest.mock import AsyncMock, MagicMock
        conn = MagicMock()
        conn.close = MagicMock()
        if ping_ok:
            conn.ping = AsyncMock(return_value=None)
        else:
            import aiomysql
            conn.ping = AsyncMock(side_effect=aiomysql.OperationalError(2006, "gone away"))
        cur = MagicMock()
        cur.__aenter__ = AsyncMock(return_value=cur)
        cur.__aexit__ = AsyncMock(return_value=None)
        if exec_err:
            cur.execute = AsyncMock(side_effect=exec_err)
        else:
            cur.execute = AsyncMock(return_value=None)
        cur.fetchone = AsyncMock(return_value=fetchone_result)
        cur.fetchmany = AsyncMock(return_value=[fetchone_result] if fetchone_result else [])
        conn.cursor = MagicMock(return_value=cur)
        return conn

    async def test_stale_conn_lost_2013_retries_and_succeeds(self, monkeypatch) -> None:
        """第 1 次 execute 抛 2013 Lost connection → conn.close() 丢弃 + 重试 → 第 2 次成功。"""
        import aiomysql
        bad_conn = await self._make_fake_conn(
            exec_err=aiomysql.OperationalError(2013, "Lost connection during query")
        )
        good_conn = await self._make_fake_conn(fetchone_result={"x": 1})
        pool = await self._make_fake_pool([bad_conn, good_conn])
        db = business_db.BusinessDB(url="mysql://x:x@h/t")
        db._pool = pool
        out = await db.fetch_one("SELECT 1", ())
        assert out == {"x": 1}
        # 坏 conn 被强制 close（不放回 pool 池里）
        bad_conn.close.assert_called_once()
        # 好 conn 走正常 release 路径，可继续复用
        assert pool.release.called

    async def test_ping_fails_swaps_conn(self, monkeypatch) -> None:
        """ping 检测出 stale conn 时直接换下一个，不浪费一次 execute 失败。"""
        bad_conn = await self._make_fake_conn(ping_ok=False)
        good_conn = await self._make_fake_conn(fetchone_result={"y": 2})
        pool = await self._make_fake_pool([bad_conn, good_conn])
        db = business_db.BusinessDB(url="mysql://x:x@h/t")
        db._pool = pool
        out = await db.fetch_one("SELECT 2", ())
        assert out == {"y": 2}
        bad_conn.close.assert_called_once()

    async def test_non_connection_error_not_retried(self, monkeypatch) -> None:
        """SQL 语法错或 1062 Duplicate 这类业务错不重试，立刻抛给上层。"""
        import aiomysql
        bad_conn = await self._make_fake_conn(
            exec_err=aiomysql.ProgrammingError(1064, "SQL syntax error")
        )
        pool = await self._make_fake_pool([bad_conn])
        db = business_db.BusinessDB(url="mysql://x:x@h/t")
        db._pool = pool
        with pytest.raises(aiomysql.ProgrammingError):
            await db.fetch_one("SELECT bad sql", ())
        # 只 acquire 一次，没有重试
        assert pool.acquire.call_count == 1

    async def test_retry_exhausted_raises(self, monkeypatch) -> None:
        """两次都拿到坏 conn，第二次仍 2013 → 抛 OperationalError。"""
        import aiomysql
        bad1 = await self._make_fake_conn(
            exec_err=aiomysql.OperationalError(2013, "Lost connection")
        )
        bad2 = await self._make_fake_conn(
            exec_err=aiomysql.OperationalError(2013, "Lost connection again")
        )
        pool = await self._make_fake_pool([bad1, bad2])
        db = business_db.BusinessDB(url="mysql://x:x@h/t")
        db._pool = pool
        with pytest.raises(aiomysql.OperationalError):
            await db.fetch_one("SELECT 1", ())
        assert pool.acquire.call_count == 2
