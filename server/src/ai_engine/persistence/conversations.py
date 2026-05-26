from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


async def create_conversation(user_type: str, subject_id: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, created_at) "
        "VALUES (:ut, :sid, :now) RETURNING id",
        {"ut": user_type, "sid": subject_id, "now": now_str()},
    )


async def get_resumable(
    conv_id: int, user_type: str, subject_id: str
) -> dict[str, object] | None:
    """恢复会话用：仅当该会话属于当前身份(user_type+subject_id)且未归档时返回 id/mode/指派客服。

    属主校验防止伪造别人的 conversation_id；archived 会话(spec §8 总结归档后)不再续接，
    让前端自然开新对话。
    """
    return await db.fetch_one(
        "SELECT id, mode, assigned_staff_id FROM conversations "
        "WHERE id=:id AND user_type=:ut AND subject_id=:sid AND COALESCE(archived,0)=0",
        {"id": conv_id, "ut": user_type, "sid": subject_id},
    )


async def get_conversation(conv_id: int) -> dict[str, object] | None:
    return await db.fetch_one(
        "SELECT id, user_type, subject_id, inferred_locale, created_at "
        "FROM conversations WHERE id=:id",
        {"id": conv_id},
    )


async def set_inferred_locale(conv_id: int, locale: str) -> None:
    """spec 6.2: runtime 每次回复后更新会话推断语言。"""
    await db.execute(
        "UPDATE conversations SET inferred_locale=:loc WHERE id=:id",
        {"loc": locale, "id": conv_id},
    )


async def append_message(conv_id: int, role: str, content: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, created_at) "
        "VALUES (:cid, :role, :content, :now) RETURNING id",
        {"cid": conv_id, "role": role, "content": content, "now": now_str()},
    )


async def append_user_turn(conv_id: int, content: str, client_message_id: str | None) -> int:
    """开启一个 AI 回合：user 消息入库，status=processing。返回 message_id(turn_id)。"""
    return await db.insert_returning_id(
        "INSERT INTO messages"
        "(conversation_id, role, content, status, client_message_id, created_at) "
        "VALUES (:cid, 'user', :content, 'processing', :cmid, :now) RETURNING id",
        {"cid": conv_id, "content": content, "cmid": client_message_id, "now": now_str()},
    )


async def finalize_turn(turn_id: int, status: str, error_code: str | None = None) -> None:
    """收尾回合：status=done/failed（failed 时带 error_code）。"""
    await db.execute(
        "UPDATE messages SET status=:st, error_code=:ec WHERE id=:id",
        {"st": status, "ec": error_code, "id": turn_id},
    )


async def set_turn_verdict(turn_id: int, verdict: str) -> None:
    """记录该回合的话题判定（yes/no/uncertain），用于留痕与知识缺口统计。"""
    await db.execute(
        "UPDATE messages SET topic_verdict=:v WHERE id=:id",
        {"v": verdict, "id": turn_id},
    )


async def find_completed_turn(conv_id: int, client_message_id: str) -> dict[str, Any] | None:
    """幂等：按 client_message_id 找已完成(status=done)的 user 回合行。"""
    return await db.fetch_one(
        "SELECT id, content FROM messages WHERE conversation_id=:cid "
        "AND client_message_id=:cmid AND role='user' AND status='done' "
        "ORDER BY id DESC LIMIT 1",
        {"cid": conv_id, "cmid": client_message_id},
    )


async def get_turn_assistant_texts(conv_id: int, turn_id: int) -> list[str]:
    """取某回合 user 行(turn_id)之后、下一条 user 行之前的所有 assistant content（原样）。"""
    rows = await db.fetch_all(
        "SELECT id, role, content FROM messages WHERE conversation_id=:cid AND id>:tid ORDER BY id",
        {"cid": conv_id, "tid": turn_id},
    )
    out: list[str] = []
    for r in rows:
        if r["role"] == "user":
            break
        if r["role"] == "assistant":
            out.append(str(r["content"]))
    return out


async def count_pending() -> int:
    """当前等待人工接管的会话数（spec §11 human_pending gauge）。"""
    row = await db.fetch_one("SELECT COUNT(*) AS n FROM conversations WHERE mode='human_pending'")
    return int(row["n"]) if row else 0


async def archive_conversation(conv_id: int) -> None:
    """spec §8: 会话过长被总结后归档老会话。"""
    await db.execute("UPDATE conversations SET archived=1 WHERE id=:id", {"id": conv_id})


async def count_user_turns(conv_id: int) -> int:
    row = await db.fetch_one(
        "SELECT COUNT(*) AS n FROM messages WHERE conversation_id=:id AND role='user'",
        {"id": conv_id},
    )
    return int(row["n"]) if row else 0


async def sum_content_chars(conv_id: int) -> int:
    row = await db.fetch_one(
        "SELECT COALESCE(SUM(LENGTH(content)),0) AS n FROM messages WHERE conversation_id=:id",
        {"id": conv_id},
    )
    return int(row["n"]) if row else 0


async def list_messages(conv_id: int) -> list[dict[str, object]]:
    return await db.fetch_all(
        "SELECT id, role, content, sender_staff_id, status, error_code, "
        "client_message_id, topic_verdict, created_at FROM messages "
        "WHERE conversation_id=:id ORDER BY id",
        {"id": conv_id},
    )


_VALID_MODES = {"ai", "human_pending", "human_takeover", "ai_draft"}


async def set_mode(conv_id: int, mode: str, assigned_staff_id: str | None = None) -> None:
    """spec §13.2 会话 mode 切换。human_takeover 时记录 assigned_at。"""
    if mode not in _VALID_MODES:
        raise ValueError("invalid mode")
    # human_takeover 才更新 assigned_at（用 Python 时间戳，方言无关）
    assigned_at = now_str() if mode == "human_takeover" else None
    await db.execute(
        "UPDATE conversations SET mode=:mode, assigned_staff_id=:sid, "
        "assigned_at=CASE WHEN :is_takeover=1 THEN :at ELSE assigned_at END "
        "WHERE id=:id",
        {
            "mode": mode,
            "sid": assigned_staff_id,
            "is_takeover": 1 if mode == "human_takeover" else 0,
            "at": assigned_at,
            "id": conv_id,
        },
    )


async def get_conversation_meta(conv_id: int) -> dict[str, object] | None:
    """客服详情页用：返回会话当前 mode / 指派人等元信息（含 mode、assigned_staff_id）。"""
    return await db.fetch_one(
        "SELECT id, user_type, subject_id, mode, assigned_staff_id, created_at "
        "FROM conversations WHERE id=:id",
        {"id": conv_id},
    )


async def get_mode(conv_id: int) -> tuple[str, str | None]:
    row = await db.fetch_one(
        "SELECT mode, assigned_staff_id FROM conversations WHERE id=:id", {"id": conv_id}
    )
    if not row:
        raise ValueError("conv not found")
    return row["mode"], row["assigned_staff_id"]


async def list_for_staff(filter_status: str = "all") -> list[dict[str, object]]:
    """客服工作台列表。filter_status ∈ {human_pending, human_takeover, all}"""
    if filter_status == "all":
        return await db.fetch_all(
            "SELECT * FROM conversations WHERE mode != 'ai' ORDER BY id DESC LIMIT 100"
        )
    return await db.fetch_all(
        "SELECT * FROM conversations WHERE mode=:m ORDER BY id DESC LIMIT 100",
        {"m": filter_status},
    )


async def save_ai_draft(conv_id: int, content: str) -> int:
    """spec §13.2 ai_draft：AI 草稿不发用户，落库待客服 review。"""
    return await append_message(conv_id, role="ai_draft", content=content)


async def get_latest_ai_draft(conv_id: int) -> str | None:
    row = await db.fetch_one(
        "SELECT content FROM messages WHERE conversation_id=:id AND role='ai_draft' "
        "ORDER BY id DESC LIMIT 1",
        {"id": conv_id},
    )
    return str(row["content"]) if row else None


async def clear_ai_drafts(conv_id: int) -> None:
    await db.execute(
        "DELETE FROM messages WHERE conversation_id=:id AND role='ai_draft'", {"id": conv_id}
    )


async def append_human_message(conv_id: int, sender_staff_id: str, content: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, sender_staff_id, created_at) "
        "VALUES (:cid, 'human_agent', :content, :sid, :now) RETURNING id",
        {"cid": conv_id, "content": content, "sid": sender_staff_id, "now": now_str()},
    )
