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
