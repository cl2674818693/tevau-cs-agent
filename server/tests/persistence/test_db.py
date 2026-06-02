"""Persistence: db.py — 异步连接池 / get_conn / fetch_one / fetch_all / execute / insert_returning_id

策略：用 `temp_db_url` 拿独立 sqlite+aiosqlite，调 init_db() 建表，然后在
真实 schema 上验证 helper。RETURNING id 需 SQLite >= 3.35（项目最低支持）。
"""

import pytest
from sqlalchemy import text

from ai_engine.persistence import db
from ai_engine.persistence.db import (
    _engine,
    execute,
    fetch_all,
    fetch_one,
    get_conn,
    init_db,
    insert_returning_id,
)
from ai_engine.persistence.schema import now_str


class TestInitDb:
    """init_db 幂等建表 + 在多 db_url 下分别建 engine。"""

    async def test_init_db_creates_tables(self, temp_db_url: str) -> None:
        """建表后能 SELECT 系统目录确认 conversations / messages / staff 等表存在。"""
        await init_db()
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            names = {row[0] for row in res.fetchall()}
        assert "conversations" in names
        assert "messages" in names
        assert "staff" in names
        assert "tool_audits" in names

    async def test_init_db_idempotent(self, temp_db_url: str) -> None:
        """重复调用不抛错，且不重复创建数据。"""
        await init_db()
        # 先插一条
        cid = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U1", "now": now_str()},
        )
        await init_db()  # 再来一次
        row = await fetch_one("SELECT id FROM conversations WHERE id=:id", {"id": cid})
        assert row is not None  # 数据未被清

    async def test_engine_cached_per_url(self, temp_db_url: str) -> None:
        """同一 db_url 取 engine 应当复用同一对象（避免连接泄漏）。"""
        await init_db()
        e1 = _engine()
        e2 = _engine()
        assert e1 is e2


class TestFetchOne:
    async def test_returns_dict(self, temp_db_url: str) -> None:
        await init_db()
        cid = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U1", "now": now_str()},
        )
        row = await fetch_one(
            "SELECT id, user_type, subject_id FROM conversations WHERE id=:id", {"id": cid}
        )
        assert row is not None
        assert row["id"] == cid
        assert row["user_type"] == "c"
        assert row["subject_id"] == "U1"

    async def test_returns_none_when_no_row(self, temp_db_url: str) -> None:
        await init_db()
        row = await fetch_one("SELECT id FROM conversations WHERE id=:id", {"id": 99999})
        assert row is None

    async def test_empty_params_dict_ok(self, temp_db_url: str) -> None:
        await init_db()
        row = await fetch_one("SELECT COUNT(*) AS n FROM conversations")
        assert row is not None and row["n"] == 0


class TestFetchAll:
    async def test_returns_list_of_dicts(self, temp_db_url: str) -> None:
        await init_db()
        ids = []
        for sid in ("U1", "U2", "U3"):
            cid = await insert_returning_id(
                "INSERT INTO conversations(user_type, subject_id, created_at) "
                "VALUES (:ut, :sid, :now) RETURNING id",
                {"ut": "c", "sid": sid, "now": now_str()},
            )
            ids.append(cid)
        rows = await fetch_all("SELECT id, subject_id FROM conversations ORDER BY id")
        assert [r["id"] for r in rows] == ids
        assert {r["subject_id"] for r in rows} == {"U1", "U2", "U3"}

    async def test_returns_empty_when_no_rows(self, temp_db_url: str) -> None:
        await init_db()
        rows = await fetch_all("SELECT id FROM conversations")
        assert rows == []


class TestExecute:
    async def test_insert_then_update(self, temp_db_url: str) -> None:
        await init_db()
        cid = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U1", "now": now_str()},
        )
        await execute(
            "UPDATE conversations SET inferred_locale=:loc WHERE id=:id",
            {"loc": "zh-CN", "id": cid},
        )
        row = await fetch_one(
            "SELECT inferred_locale FROM conversations WHERE id=:id", {"id": cid}
        )
        assert row is not None and row["inferred_locale"] == "zh-CN"

    async def test_update_nonexistent_row_no_error(self, temp_db_url: str) -> None:
        """UPDATE 命中 0 行不抛错（execute 不返回受影响行数）。"""
        await init_db()
        await execute(
            "UPDATE conversations SET inferred_locale=:loc WHERE id=:id",
            {"loc": "en", "id": 99999},
        )

    async def test_delete(self, temp_db_url: str) -> None:
        await init_db()
        cid = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U1", "now": now_str()},
        )
        await execute("DELETE FROM conversations WHERE id=:id", {"id": cid})
        row = await fetch_one("SELECT id FROM conversations WHERE id=:id", {"id": cid})
        assert row is None


class TestInsertReturningId:
    async def test_returns_pk(self, temp_db_url: str) -> None:
        await init_db()
        cid = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "b", "sid": "BU1", "now": now_str()},
        )
        assert isinstance(cid, int)
        assert cid > 0

    async def test_two_inserts_get_different_ids(self, temp_db_url: str) -> None:
        await init_db()
        a = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U1", "now": now_str()},
        )
        b = await insert_returning_id(
            "INSERT INTO conversations(user_type, subject_id, created_at) "
            "VALUES (:ut, :sid, :now) RETURNING id",
            {"ut": "c", "sid": "U2", "now": now_str()},
        )
        assert a != b

    async def test_check_constraint_violation(self, temp_db_url: str) -> None:
        """user_type CHECK 约束（仅允许 c/b/g）违例应抛错。"""
        await init_db()
        with pytest.raises(Exception):  # noqa: B017 SQLite 抛 IntegrityError，PG 抛 CheckViolation
            await insert_returning_id(
                "INSERT INTO conversations(user_type, subject_id, created_at) "
                "VALUES (:ut, :sid, :now) RETURNING id",
                {"ut": "x", "sid": "U1", "now": now_str()},
            )


class TestGetConn:
    """get_conn 是事务上下文：退出即 commit。"""

    async def test_transaction_commits_on_exit(self, temp_db_url: str) -> None:
        await init_db()
        async with get_conn() as conn:
            await conn.execute(
                text(
                    "INSERT INTO conversations(user_type, subject_id, created_at) "
                    "VALUES (:ut, :sid, :now)"
                ),
                {"ut": "c", "sid": "TX1", "now": now_str()},
            )
        # 上下文外应可读到
        row = await fetch_one(
            "SELECT id FROM conversations WHERE subject_id=:sid", {"sid": "TX1"}
        )
        assert row is not None


class TestDbModuleExports:
    """db 模块对外接口面：fetch_one / fetch_all / execute / insert_returning_id / get_conn / init_db。"""

    def test_public_symbols_present(self) -> None:
        for name in ("fetch_one", "fetch_all", "execute", "insert_returning_id", "get_conn", "init_db"):
            assert hasattr(db, name), f"db missing {name}"
