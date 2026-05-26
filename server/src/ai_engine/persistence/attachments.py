"""attachments DAO：上传时建行(message_id NULL)，发送时按归属+未绑定原子绑定。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_attachment(
    conv_id: int,
    uploader_type: str,
    uploader_id: str,
    object_key: str,
    mime: str,
    byte_size: int,
    sha256: str,
) -> int:
    return await db.insert_returning_id(
        "INSERT INTO attachments"
        "(conversation_id, uploader_type, uploader_id, object_key, mime, byte_size, sha256, "
        "created_at) VALUES (:cid, :ut, :uid, :key, :mime, :sz, :sha, :now) RETURNING id",
        {
            "cid": conv_id,
            "ut": uploader_type,
            "uid": uploader_id,
            "key": object_key,
            "mime": mime,
            "sz": byte_size,
            "sha": sha256,
            "now": now_str(),
        },
    )


async def bind_attachments(
    message_id: int, conv_id: int, uploader_id: str, attachment_ids: list[int]
) -> list[dict[str, Any]]:
    """把未绑定且归属匹配的附件绑到 message_id。逐条 UPDATE ... WHERE message_id IS NULL
    保证幂等/防重复绑定；返回成功绑定的行。"""
    bound: list[dict[str, Any]] = []
    for aid in attachment_ids:
        await db.execute(
            "UPDATE attachments SET message_id=:mid WHERE id=:aid AND conversation_id=:cid "
            "AND uploader_id=:uid AND message_id IS NULL",
            {"mid": message_id, "aid": aid, "cid": conv_id, "uid": uploader_id},
        )
        row = await db.fetch_one(
            "SELECT id, object_key, mime, byte_size FROM attachments "
            "WHERE id=:aid AND message_id=:mid",
            {"aid": aid, "mid": message_id},
        )
        if row:
            bound.append(row)
    return bound


async def list_message_attachments(message_id: int) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, object_key, mime, byte_size FROM attachments "
        "WHERE message_id=:mid ORDER BY id",
        {"mid": message_id},
    )


async def get_attachment(attachment_id: int) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, conversation_id, object_key, mime FROM attachments WHERE id=:aid",
        {"aid": attachment_id},
    )


async def list_for_conversation(conv_id: int) -> dict[int, list[dict[str, Any]]]:
    """客服历史/日志批量取：message_id -> [attachment...]。未绑定(NULL)的跳过。"""
    rows = await db.fetch_all(
        "SELECT id, message_id, mime FROM attachments "
        "WHERE conversation_id=:cid AND message_id IS NOT NULL ORDER BY id",
        {"cid": conv_id},
    )
    out: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(int(r["message_id"]), []).append({"id": r["id"], "mime": r["mime"]})
    return out
