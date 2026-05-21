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


async def count_pending() -> int:
    """当前等待人工接管的会话数（spec §11 human_pending gauge）。"""
    async with get_conn() as conn:
        row = await (
            await conn.execute("SELECT COUNT(*) AS n FROM conversations WHERE mode='human_pending'")
        ).fetchone()
    return int(row["n"]) if row else 0


async def archive_conversation(conv_id: int) -> None:
    """spec §8: 会话过长被总结后归档老会话。"""
    async with get_conn() as conn:
        await conn.execute("UPDATE conversations SET archived=1 WHERE id=?", (conv_id,))
        await conn.commit()


async def count_user_turns(conv_id: int) -> int:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE conversation_id=? AND role='user'",
                (conv_id,),
            )
        ).fetchone()
    return int(row["n"]) if row else 0


async def sum_content_chars(conv_id: int) -> int:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT COALESCE(SUM(LENGTH(content)),0) AS n "
                "FROM messages WHERE conversation_id=?",
                (conv_id,),
            )
        ).fetchone()
    return int(row["n"]) if row else 0


async def list_messages(conv_id: int) -> list[dict[str, object]]:
    async with get_conn() as conn:
        rows = await (
            await conn.execute(
                "SELECT id, role, content, sender_staff_id, created_at FROM messages "
                "WHERE conversation_id=? ORDER BY id",
                (conv_id,),
            )
        ).fetchall()
    return [dict(r) for r in rows]


_VALID_MODES = {"ai", "human_pending", "human_takeover", "ai_draft"}


async def set_mode(conv_id: int, mode: str, assigned_staff_id: str | None = None) -> None:
    """spec §13.2 会话 mode 切换。human_takeover 时记录 assigned_at。"""
    if mode not in _VALID_MODES:
        raise ValueError("invalid mode")
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE conversations SET mode=?, assigned_staff_id=?, "
            "assigned_at=CASE WHEN ?=? THEN datetime('now') ELSE assigned_at END "
            "WHERE id=?",
            (mode, assigned_staff_id, mode, "human_takeover", conv_id),
        )
        await conn.commit()


async def get_mode(conv_id: int) -> tuple[str, str | None]:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT mode, assigned_staff_id FROM conversations WHERE id=?", (conv_id,)
            )
        ).fetchone()
    if not row:
        raise ValueError("conv not found")
    return row["mode"], row["assigned_staff_id"]


async def list_for_staff(filter_status: str = "all") -> list[dict[str, object]]:
    """客服工作台列表。filter_status ∈ {human_pending, human_takeover, all}"""
    async with get_conn() as conn:
        if filter_status == "all":
            rows = await (
                await conn.execute(
                    "SELECT * FROM conversations WHERE mode != 'ai' ORDER BY id DESC LIMIT 100"
                )
            ).fetchall()
        else:
            rows = await (
                await conn.execute(
                    "SELECT * FROM conversations WHERE mode=? ORDER BY id DESC LIMIT 100",
                    (filter_status,),
                )
            ).fetchall()
    return [dict(r) for r in rows]


async def save_ai_draft(conv_id: int, content: str) -> int:
    """spec §13.2 ai_draft：AI 草稿不发用户，落库待客服 review。"""
    return await append_message(conv_id, role="ai_draft", content=content)


async def get_latest_ai_draft(conv_id: int) -> str | None:
    async with get_conn() as conn:
        row = await (
            await conn.execute(
                "SELECT content FROM messages WHERE conversation_id=? AND role='ai_draft' "
                "ORDER BY id DESC LIMIT 1",
                (conv_id,),
            )
        ).fetchone()
    return str(row["content"]) if row else None


async def clear_ai_drafts(conv_id: int) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "DELETE FROM messages WHERE conversation_id=? AND role='ai_draft'", (conv_id,)
        )
        await conn.commit()


async def append_human_message(conv_id: int, sender_staff_id: str, content: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO messages(conversation_id, role, content, sender_staff_id) "
            "VALUES (?,?,?,?)",
            (conv_id, "human_agent", content, sender_staff_id),
        )
        await conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid
