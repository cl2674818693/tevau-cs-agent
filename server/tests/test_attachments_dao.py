from ai_engine.persistence import attachments as att
from ai_engine.persistence import conversations as conv_dao
from ai_engine.persistence.db import init_db


async def test_create_bind_and_list(temp_db_url):
    await init_db()
    cid = await conv_dao.create_conversation("c", "u-1")
    aid = await att.create_attachment(cid, "c", "u-1", "uploads/x.png", "image/png", 10, "deadbeef")
    assert isinstance(aid, int)

    mid = await conv_dao.append_user_turn(cid, "看这张图", None)
    bound = await att.bind_attachments(mid, cid, "u-1", [aid])
    assert [b["id"] for b in bound] == [aid]

    listed = await att.list_message_attachments(mid)
    assert listed[0]["object_key"] == "uploads/x.png"

    conv_map = await att.list_for_conversation(cid)
    assert mid in conv_map
    assert conv_map[mid][0]["id"] == aid
    assert conv_map[mid][0]["mime"] == "image/png"


async def test_bind_rejects_cross_conversation_and_double_bind(temp_db_url):
    await init_db()
    cid = await conv_dao.create_conversation("c", "u-1")
    other = await conv_dao.create_conversation("c", "u-2")
    aid = await att.create_attachment(cid, "c", "u-1", "uploads/y.png", "image/png", 10, "ab")
    mid = await conv_dao.append_user_turn(cid, "x", None)

    # 别的会话/别的上传者绑不动
    assert await att.bind_attachments(mid, other, "u-1", [aid]) == []
    assert await att.bind_attachments(mid, cid, "u-2", [aid]) == []
    # 正确绑定一次成功
    assert len(await att.bind_attachments(mid, cid, "u-1", [aid])) == 1
    # 已绑定再绑无效（message_id 已非 NULL）
    mid2 = await conv_dao.append_user_turn(cid, "x2", None)
    assert await att.bind_attachments(mid2, cid, "u-1", [aid]) == []
