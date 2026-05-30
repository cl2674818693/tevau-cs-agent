"""知识库 CRUD + 工具优先读取。"""

from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def upsert_entry(
    type_: str,
    key: str,
    title: str,
    content: str,
    locale: str = "zh",
    created_by: str | None = None,
    source_gap_signal: str | None = None,
) -> int:
    """按 (type, key, locale, status='draft') upsert 草稿；返回 id。"""
    existing = await db.fetch_one(
        "SELECT id FROM knowledge_entries "
        "WHERE type = :t AND key = :k AND locale = :l AND status = 'draft'",
        {"t": type_, "k": key, "l": locale},
    )
    if existing is not None:
        await db.execute(
            "UPDATE knowledge_entries SET title = :ti, content = :c, updated_at = :now "
            "WHERE id = :id",
            {"ti": title, "c": content, "now": now_str(), "id": existing["id"]},
        )
        return int(existing["id"])
    return await db.insert_returning_id(
        "INSERT INTO knowledge_entries(type, key, title, content, locale, status, "
        "source_gap_signal, created_by, updated_at) "
        "VALUES (:t, :k, :ti, :c, :l, 'draft', :gs, :by, :now) RETURNING id",
        {
            "t": type_, "k": key, "ti": title, "c": content, "l": locale,
            "gs": source_gap_signal, "by": created_by, "now": now_str(),
        },
    )


async def publish(entry_id: int) -> None:
    await db.execute(
        "UPDATE knowledge_entries SET status = 'published', updated_at = :now "
        "WHERE id = :id",
        {"now": now_str(), "id": int(entry_id)},
    )


async def get_published(type_: str, key: str, locale: str = "zh") -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, title, content, updated_at FROM knowledge_entries "
        "WHERE type = :t AND key = :k AND locale = :l AND status = 'published' "
        "ORDER BY id DESC LIMIT 1",
        {"t": type_, "k": key, "l": locale},
    )


async def list_entries(
    type_: str | None = None, status: str | None = None, limit: int = 200,
) -> list[dict[str, Any]]:
    return await db.fetch_all(
        "SELECT id, type, key, title, locale, status, source_gap_signal, "
        "created_by, updated_at FROM knowledge_entries "
        "WHERE (CAST(:t AS TEXT) IS NULL OR type = :t) "
        "AND (CAST(:s AS TEXT) IS NULL OR status = :s) "
        "ORDER BY id DESC LIMIT :lim",
        {"t": type_, "s": status, "lim": limit},
    )


async def delete_entry(entry_id: int) -> None:
    await db.execute(
        "DELETE FROM knowledge_entries WHERE id = :id", {"id": int(entry_id)}
    )
