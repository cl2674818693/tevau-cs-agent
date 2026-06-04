"""Persistence: client_info.py — 会话客户端信息 upsert（H5 上报 → admin 详情卡读）。

覆盖：upsert_client_info（原子 ON CONFLICT 覆盖语义、并发不撞主键）, get_client_info,
NULL 字段透传。
"""

import asyncio

import pytest

from ai_engine.persistence import client_info, conversations as conv
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestUpsert:
    async def test_first_insert(self, db_ready, conv_id) -> None:
        await client_info.upsert_client_info(
            conv_id, "ios", "1.2.3", "Mozilla/5.0 ..."
        )
        row = await client_info.get_client_info(conv_id)
        assert row is not None
        assert row["platform"] == "ios"
        assert row["app_version"] == "1.2.3"
        assert row["user_agent"] == "Mozilla/5.0 ..."

    async def test_overwrite(self, db_ready, conv_id) -> None:
        await client_info.upsert_client_info(conv_id, "android", "1.0.0", "ua1")
        await client_info.upsert_client_info(conv_id, "ios", "2.0.0", "ua2")
        row = await client_info.get_client_info(conv_id)
        assert row is not None
        assert row["platform"] == "ios"
        assert row["app_version"] == "2.0.0"
        assert row["user_agent"] == "ua2"

    async def test_updated_at_changes_on_reupsert(self, db_ready, conv_id) -> None:
        await client_info.upsert_client_info(conv_id, "ios", "1.0.0", "ua")
        t1 = (await client_info.get_client_info(conv_id))["updated_at"]
        await asyncio.sleep(1.05)
        await client_info.upsert_client_info(conv_id, "ios", "1.0.0", "ua")
        t2 = (await client_info.get_client_info(conv_id))["updated_at"]
        assert t2 > t1

    async def test_null_fields(self, db_ready, conv_id) -> None:
        await client_info.upsert_client_info(conv_id, None, None, None)
        row = await client_info.get_client_info(conv_id)
        assert row is not None
        assert row["platform"] is None
        assert row["app_version"] is None
        assert row["user_agent"] is None

    async def test_isolated_per_conversation(self, db_ready) -> None:
        c1 = await conv.create_conversation("c", "U1")
        c2 = await conv.create_conversation("c", "U2")
        await client_info.upsert_client_info(c1, "ios", "1.0.0", "ua1")
        await client_info.upsert_client_info(c2, "android", "2.0.0", "ua2")
        r1 = await client_info.get_client_info(c1)
        r2 = await client_info.get_client_info(c2)
        assert r1 is not None and r1["platform"] == "ios"
        assert r2 is not None and r2["platform"] == "android"

    async def test_concurrent_upsert_no_pk_conflict(self, db_ready, conv_id) -> None:
        """React StrictMode 双 mount / 重连重发会让 reportClientInfo 几乎同时进两次。
        历史实现走 DELETE+INSERT 非原子，第二条 INSERT 会撞主键 500。
        ON CONFLICT 原子 upsert 必须吃下并发：两个 future 都成功返回，行只剩一条。"""
        await asyncio.gather(
            client_info.upsert_client_info(conv_id, "ios", "1.0.0", "ua-A"),
            client_info.upsert_client_info(conv_id, "ios", "1.0.0", "ua-B"),
        )
        row = await client_info.get_client_info(conv_id)
        assert row is not None
        # 最终落到的 user_agent 是 A/B 之一即可（具体哪一条赢由调度决定，不断言）
        assert row["user_agent"] in {"ua-A", "ua-B"}


class TestGetClientInfo:
    async def test_missing_returns_none(self, db_ready, conv_id) -> None:
        assert await client_info.get_client_info(conv_id) is None

    async def test_missing_conv_returns_none(self, db_ready) -> None:
        assert await client_info.get_client_info(99999) is None
