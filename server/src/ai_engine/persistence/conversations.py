from ai_engine.persistence.db import get_conn


async def create_conversation(user_type: str, subject_id: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO conversations(user_type, subject_id) VALUES (?, ?)",
            (user_type, subject_id),
        )
        await conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid


async def get_conversation(conv_id: int) -> dict[str, object] | None:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT id, user_type, subject_id, inferred_locale, created_at "
                "FROM conversations WHERE id=?",
                (conv_id,),
            )
        ).fetchone()
    return dict(row) if row else None


async def set_inferred_locale(conv_id: int, locale: str) -> None:
    """spec 6.2: runtime 每次回复后更新会话推断语言。"""
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE conversations SET inferred_locale=? WHERE id=?", (locale, conv_id)
        )
        await conn.commit()


async def append_message(conv_id: int, role: str, content: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, content),
        )
        await conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid


async def list_messages(conv_id: int) -> list[dict[str, object]]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, role, content, created_at FROM messages "
                "WHERE conversation_id=? ORDER BY id",
                (conv_id,),
            )
        ).fetchall()
    return [dict(r) for r in rows]
