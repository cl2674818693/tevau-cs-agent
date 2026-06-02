"""Persistence: attachments.py — 附件上传 / 绑定 / 列表。

覆盖：create_attachment, bind_attachments（仅未绑定 + 归属匹配, 重复绑定幂等）,
list_message_attachments, get_attachment, list_for_conversation。
"""

import pytest

from ai_engine.persistence import attachments as att, conversations as conv
from ai_engine.persistence.db import init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


@pytest.fixture
async def conv_id(db_ready):
    return await conv.create_conversation("c", "U1")


class TestCreateAttachment:
    async def test_create_returns_pk(self, db_ready, conv_id) -> None:
        aid = await att.create_attachment(
            conv_id, "c", "U1", "key/abc", "image/png", 1024, "sha"
        )
        assert aid > 0
        row = await att.get_attachment(aid)
        assert row is not None
        assert row["object_key"] == "key/abc"
        assert row["mime"] == "image/png"

    async def test_create_unbound_message_id_null(self, db_ready, conv_id) -> None:
        aid = await att.create_attachment(conv_id, "c", "U1", "k", "image/png", 1, "s")
        # 未绑定时 list_message_attachments(None) 不返回
        rows = await att.list_for_conversation(conv_id)
        assert rows == {}


class TestBindAttachments:
    async def test_bind_basic(self, db_ready, conv_id) -> None:
        a1 = await att.create_attachment(conv_id, "c", "U1", "k1", "image/png", 1, "s")
        a2 = await att.create_attachment(conv_id, "c", "U1", "k2", "image/png", 1, "s")
        mid = await conv.append_message(conv_id, "user", "with images")
        bound = await att.bind_attachments(mid, conv_id, "U1", [a1, a2])
        assert {b["id"] for b in bound} == {a1, a2}
        rows = await att.list_message_attachments(mid)
        assert {r["id"] for r in rows} == {a1, a2}

    async def test_rebind_idempotent(self, db_ready, conv_id) -> None:
        """已绑定的附件再次 bind 同 message_id：仍可读到（成功路径），不抛错。"""
        aid = await att.create_attachment(conv_id, "c", "U1", "k", "image/png", 1, "s")
        mid = await conv.append_message(conv_id, "user", "x")
        first = await att.bind_attachments(mid, conv_id, "U1", [aid])
        second = await att.bind_attachments(mid, conv_id, "U1", [aid])
        assert first and second  # 两次都拿得到行（第二次走 UPDATE 0 行但 SELECT 仍然命中）

    async def test_cannot_steal_other_uploaders(self, db_ready, conv_id) -> None:
        """归属不匹配（uploader_id 不一致）→ UPDATE 0 行，SELECT 拿不到。"""
        aid = await att.create_attachment(conv_id, "c", "U1", "k", "image/png", 1, "s")
        mid = await conv.append_message(conv_id, "user", "x")
        bound = await att.bind_attachments(mid, conv_id, "U2", [aid])  # 不是 uploader
        assert bound == []

    async def test_cannot_rebind_to_different_message(self, db_ready, conv_id) -> None:
        """已绑定到 m1 的附件，再绑 m2：WHERE message_id IS NULL 不命中 → 不动。"""
        aid = await att.create_attachment(conv_id, "c", "U1", "k", "image/png", 1, "s")
        m1 = await conv.append_message(conv_id, "user", "a")
        m2 = await conv.append_message(conv_id, "user", "b")
        await att.bind_attachments(m1, conv_id, "U1", [aid])
        bound = await att.bind_attachments(m2, conv_id, "U1", [aid])
        assert bound == []  # 已被 m1 占住
        # m1 仍持有
        rows = await att.list_message_attachments(m1)
        assert [r["id"] for r in rows] == [aid]


class TestListForConversation:
    async def test_grouped_by_message(self, db_ready, conv_id) -> None:
        a1 = await att.create_attachment(conv_id, "c", "U1", "k1", "image/png", 1, "s")
        a2 = await att.create_attachment(conv_id, "c", "U1", "k2", "image/png", 1, "s")
        m1 = await conv.append_message(conv_id, "user", "a")
        m2 = await conv.append_message(conv_id, "user", "b")
        await att.bind_attachments(m1, conv_id, "U1", [a1])
        await att.bind_attachments(m2, conv_id, "U1", [a2])
        grouped = await att.list_for_conversation(conv_id)
        assert sorted(grouped.keys()) == sorted([m1, m2])
        assert grouped[m1][0]["id"] == a1

    async def test_excludes_unbound(self, db_ready, conv_id) -> None:
        await att.create_attachment(conv_id, "c", "U1", "k", "image/png", 1, "s")
        assert await att.list_for_conversation(conv_id) == {}


class TestGetAttachment:
    async def test_missing_returns_none(self, db_ready) -> None:
        assert await att.get_attachment(99999) is None
