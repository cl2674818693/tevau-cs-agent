"""Prompt 草稿 / 发布 persistence。

读取语义：get_published(version, file_name) 取最新一条 status=published（按 id DESC）。
loader 调用此函数得到 DB 内容；缺失则回退文件读取。
"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_draft(version: str, file_name: str, content: str, editor: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO prompt_drafts(version, file_name, content, status, editor, created_at) "
        "VALUES (:v, :f, :c, 'draft', :e, :now) RETURNING id",
        {"v": version, "f": file_name, "c": content, "e": editor, "now": now_str()},
    )


async def list_by_version(version: str) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, version, file_name, content, status, editor, created_at "
        "FROM prompt_drafts WHERE version = :v ORDER BY id DESC",
        {"v": version},
    )


async def publish(draft_id: int, editor: str) -> None:
    await db.execute(
        "UPDATE prompt_drafts SET status = 'published', editor = :e WHERE id = :id",
        {"e": editor, "id": int(draft_id)},
    )


async def get_published(version: str, file_name: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, content, editor, created_at FROM prompt_drafts "
        "WHERE version = :v AND file_name = :f AND status = 'published' "
        "ORDER BY id DESC LIMIT 1",
        {"v": version, "f": file_name},
    )


async def delete_draft(draft_id: int) -> None:
    await db.execute(
        "DELETE FROM prompt_drafts WHERE id = :id", {"id": int(draft_id)}
    )
