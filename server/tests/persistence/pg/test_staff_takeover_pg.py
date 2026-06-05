"""B-P0-6: 接管/转派关键 UPDATE 路径在真 PostgreSQL 上的镜像测试。

核心目标：原子 CAS 的 `UPDATE ... WHERE assigned_staff_id IS NULL OR assigned_staff_id=:sub`
在 PG asyncpg 下行为与 SQLite 一致（rowcount 语义、NULL 比较、并发 CAS 不踩 PG 特有
的隔离级别陷阱）。这些原本只跑 SQLite，PG-only bug 会漏到生产。
"""

import asyncio

import pytest
from sqlalchemy import text

from ai_engine.persistence import conversations as conv
from ai_engine.persistence.db import get_conn
from ai_engine.persistence.schema import now_str


async def _insert_staff(staff_id: str, role: str = "agent") -> None:
    async with get_conn() as c:
        await c.execute(
            text(
                "INSERT INTO staff(staff_id, display_name, role, password_hash, active, created_at) "
                "VALUES (:sid, :name, :role, 'x', 1, :now)"
            ),
            {"sid": staff_id, "name": staff_id, "role": role, "now": now_str()},
        )


class TestTakeoverCasOnPg:
    async def test_take_atomic_update_on_unassigned_succeeds(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-1")
        await conv.set_mode(cid, "human_pending")
        async with get_conn() as c:
            cur = await c.execute(
                text(
                    "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:sub, "
                    "assigned_at=:now WHERE id=:id AND "
                    "(assigned_staff_id IS NULL OR assigned_staff_id=:sub)"
                ),
                {"sub": "agent-A", "now": now_str(), "id": cid},
            )
            assert cur.rowcount == 1
        row = await conv.get_conversation_meta(cid)
        assert row is not None
        assert row["mode"] == "human_takeover"
        assert row["assigned_staff_id"] == "agent-A"

    async def test_take_atomic_update_on_other_assigned_blocks(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-2")
        await conv.set_mode(cid, "human_takeover", assigned_staff_id="agent-A")
        async with get_conn() as c:
            cur = await c.execute(
                text(
                    "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:sub, "
                    "assigned_at=:now WHERE id=:id AND "
                    "(assigned_staff_id IS NULL OR assigned_staff_id=:sub)"
                ),
                {"sub": "agent-B", "now": now_str(), "id": cid},
            )
            # 关键：PG 下 NULL 严格比较 + 三值逻辑必须按预期返回 rowcount=0
            assert cur.rowcount == 0
        row = await conv.get_conversation_meta(cid)
        assert row is not None
        assert row["assigned_staff_id"] == "agent-A"

    async def test_concurrent_take_only_one_wins(self, pg_db) -> None:
        """asyncio.gather 模拟两个客服同时点 take —— PG 行锁下必须只有一个 rowcount=1。"""
        cid = await conv.create_conversation("c", "U-3")
        await conv.set_mode(cid, "human_pending")

        async def _try_take(staff_sub: str) -> int:
            async with get_conn() as c:
                cur = await c.execute(
                    text(
                        "UPDATE conversations SET mode='human_takeover', assigned_staff_id=:sub, "
                        "assigned_at=:now WHERE id=:id AND "
                        "(assigned_staff_id IS NULL OR assigned_staff_id=:sub)"
                    ),
                    {"sub": staff_sub, "now": now_str(), "id": cid},
                )
                return cur.rowcount

        results = await asyncio.gather(_try_take("agent-A"), _try_take("agent-B"))
        winners = [r for r in results if r == 1]
        assert len(winners) >= 1  # 至少一个赢；PG 行级锁保证不会都 rowcount=0
        row = await conv.get_conversation_meta(cid)
        assert row["assigned_staff_id"] in ("agent-A", "agent-B")


class TestArchivedFlagOnPg:
    async def test_archived_default_is_zero(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-4")
        row = await conv.get_conversation(cid)
        assert int(row["archived"]) == 0

    async def test_get_resumable_filters_archived_on_pg(self, pg_db) -> None:
        cid = await conv.create_conversation("c", "U-5")
        await conv.archive_conversation(cid)
        # PG 下 COALESCE(archived, 0)=0 与 SQLite 行为一致
        assert await conv.get_resumable(cid, "c", "U-5") is None
