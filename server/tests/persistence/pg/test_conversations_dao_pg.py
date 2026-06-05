"""B-P0-6: 关键 DAO 在真 PostgreSQL 上的行为镜像 SQLite 单元测试。

历史曾被 PG-only 的 `CAST(:p AS TEXT) IS NULL` 类型歧义 bug 漏过，本套件防回归：
- `get_conversation` SELECT 含 archived 列在 PG 下也能正常 fetch；
- `archive_conversation` UPDATE 在 PG 下生效；
- `find_completed_turn` 幂等查询 PG 行为与 SQLite 一致。

这些原本只跑 SQLite，对 PG 类型差异看不见。
"""

import pytest

from ai_engine.persistence import conversations as conv


class TestConversationsDaoOnPg:
    async def test_get_conversation_returns_archived_column(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-PG-1")
        row = await conv.get_conversation(cid)
        assert row is not None
        # archived 列必须存在且默认 0（在 PG 下 SELECT 的列名/类型与 SQLite 行为一致）
        assert int(row["archived"]) == 0

    async def test_archive_then_get_returns_archived_true(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-PG-2")
        await conv.archive_conversation(cid)
        row = await conv.get_conversation(cid)
        assert row is not None
        assert int(row["archived"]) == 1

    async def test_find_completed_turn_with_no_message_returns_none(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-PG-3")
        # 查不存在的 client_message_id —— PG 下 NULL 比较语义不能让查询误中
        row = await conv.find_completed_turn(cid, "never-used-cmid")
        assert row is None

    async def test_get_resumable_filters_archived(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-PG-4")
        # archived=0 → 可恢复
        r1 = await conv.get_resumable(cid, "c", "U-PG-4")
        assert r1 is not None and int(r1["id"]) == cid
        # archived 后 → None
        await conv.archive_conversation(cid)
        r2 = await conv.get_resumable(cid, "c", "U-PG-4")
        assert r2 is None
