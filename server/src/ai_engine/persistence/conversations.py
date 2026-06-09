import json
from typing import Any

from ai_engine.persistence import db
from ai_engine.persistence.schema import now_str


def message_content_text(role: str, content: str) -> str:
    """把一条已落库消息的 content 还原成纯文本。

    assistant 入库的是 json.dumps([{"type":"text","text":...}])（见 agent.runtime），
    需拆出 text 块拼接；human_agent / user 原样返回。runtime 与历史接口共用，避免多处重复。
    """
    if role != "assistant":
        return content
    try:
        blocks = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    if isinstance(blocks, list):
        return "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )
    return content


async def create_conversation(user_type: str, subject_id: str) -> int:
    return await db.insert_returning_id(
        "INSERT INTO conversations(user_type, subject_id, created_at) "
        "VALUES (:ut, :sid, :now)",
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
        "SELECT id, user_type, subject_id, inferred_locale, "
        "COALESCE(archived, 0) AS archived, created_at "
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
    """写一条消息行。"""
    return await db.insert_returning_id(
        "INSERT INTO messages(conversation_id, role, content, created_at) "
        "VALUES (:cid, :role, :content, :now)",
        {
            "cid": conv_id,
            "role": role,
            "content": content,
            "now": now_str(),
        },
    )


async def append_user_turn(conv_id: int, content: str, client_message_id: str | None) -> int:
    """开启一个 AI 回合：user 消息入库，status=processing。返回 message_id(turn_id)。"""
    return await db.insert_returning_id(
        "INSERT INTO messages"
        "(conversation_id, role, content, status, client_message_id, created_at) "
        "VALUES (:cid, 'user', :content, 'processing', :cmid, :now)",
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


async def mark_needs_review(conv_id: int) -> None:
    """👎 反馈触发：标记会话待运营复核，供工作台筛选。"""
    await db.execute(
        "UPDATE conversations SET needs_review=1 WHERE id=:id", {"id": conv_id}
    )


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


async def list_messages_page(
    conv_id: int, limit: int, before_id: int | None = None
) -> list[dict[str, object]]:
    """留痕分页：取 id < before_id 的最近 limit 条（before_id=None 取最新 limit 条），
    升序返回。前端首屏取最新一页，往上"加载更早"传 before_id=当前最旧消息 id。"""
    clause = "conversation_id=:id" + (" AND id < :bid" if before_id is not None else "")
    binds: dict[str, object] = {"id": conv_id, "n": limit}
    if before_id is not None:
        binds["bid"] = before_id
    rows = await db.fetch_all(
        "SELECT id, role, content, sender_staff_id, status, error_code, "
        "client_message_id, topic_verdict, created_at FROM messages "
        f"WHERE {clause} ORDER BY id DESC LIMIT :n",
        binds,
    )
    return list(reversed(rows))


async def list_recent_messages(conv_id: int, limit: int) -> list[dict[str, object]]:
    """取最近 limit 条消息（按 id 升序返回）。历史回放用，避免长会话全量返回。"""
    rows = await db.fetch_all(
        "SELECT id, role, content, sender_staff_id, status, error_code, "
        "client_message_id, topic_verdict, created_at FROM messages "
        "WHERE conversation_id=:id ORDER BY id DESC LIMIT :n",
        {"id": conv_id, "n": limit},
    )
    return list(reversed(rows))


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


async def get_meta_with_risk(conv_id: int) -> dict[str, object] | None:
    """详情页右侧信息卡用：元信息 + 风险信号（与列表页 list_for_staff 同一套口径）。"""
    return await db.fetch_one(
        f"SELECT c.id, c.user_type, c.subject_id, c.mode, c.assigned_staff_id, "
        f"c.assigned_at, c.needs_review, c.created_at, {_RISK_SELECT} "
        "FROM conversations c WHERE c.id=:id",
        {"id": conv_id},
    )


async def get_mode(conv_id: int) -> tuple[str, str | None]:
    row = await db.fetch_one(
        "SELECT mode, assigned_staff_id FROM conversations WHERE id=:id", {"id": conv_id}
    )
    if not row:
        raise ValueError("conv not found")
    return row["mode"], row["assigned_staff_id"]


# 每会话风险信号子查询（EXISTS 避免 JOIN 行膨胀；SQLite/Postgres 均兼容）。
# 字段全为固定字符串、绑定参数仅会话维度，不拼用户输入。
_RISK_SELECT = (
    "EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=c.id "
    "AND m.status='failed') AS has_failed, "
    "EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=c.id "
    "AND m.topic_verdict='no') AS has_out_of_scope, "
    "EXISTS(SELECT 1 FROM message_feedback f WHERE f.conversation_id=c.id "
    "AND f.rating='down') AS has_downvote, "
    "EXISTS(SELECT 1 FROM tool_audits t WHERE t.conversation_id=c.id "
    "AND t.is_empty=1) AS has_empty_tool"
)
# risk_only=True 的 WHERE：任一风险信号为真（含 needs_review）。不受 mode 限制，
# 因此 mode='ai' 但答错的会话也能被选出。
_RISK_WHERE = (
    "(c.needs_review=1 "
    "OR EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.status='failed') "
    "OR EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.topic_verdict='no') "
    "OR EXISTS(SELECT 1 FROM message_feedback f WHERE f.conversation_id=c.id "
    "AND f.rating='down') "
    "OR EXISTS(SELECT 1 FROM tool_audits t WHERE t.conversation_id=c.id AND t.is_empty=1))"
)


async def list_for_staff(
    filter_status: str = "all",
    risk_only: bool = False,
    me: str | None = None,
) -> list[dict[str, object]]:
    """客服工作台列表。

    - filter_status ∈ {human_pending, human_takeover, all}：默认 mode 过滤（risk_only=False）。
    - risk_only=True：忽略 mode，按"任一风险信号为真"筛选（含 mode='ai' 的答错会话）。
    - me：当 filter_status='human_pending' 时，只返回开放池或派给我的会话（隔离别人未到期的派单）。

    无论何种过滤，每行都附带风险标记字段：has_failed / has_out_of_scope /
    has_downvote / has_empty_tool（needs_review 为表自身列，随 c.* 返回）。
    """
    cols = f"c.*, {_RISK_SELECT}"
    if risk_only:
        return await db.fetch_all(
            f"SELECT {cols} FROM conversations c WHERE {_RISK_WHERE} "
            "ORDER BY c.id DESC LIMIT 100"
        )
    if filter_status == "all":
        return await db.fetch_all(
            f"SELECT {cols} FROM conversations c WHERE c.mode != 'ai' ORDER BY c.id DESC LIMIT 100"
        )
    if filter_status == "human_pending" and me:
        return await db.fetch_all(
            f"SELECT {cols} FROM conversations c WHERE c.mode='human_pending' "
            f"AND (c.assigned_staff_id IS NULL OR c.assigned_staff_id=:me) "
            f"ORDER BY c.id DESC LIMIT 100",
            {"me": me},
        )
    return await db.fetch_all(
        f"SELECT {cols} FROM conversations c WHERE c.mode=:m ORDER BY c.id DESC LIMIT 100",
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
        "VALUES (:cid, 'human_agent', :content, :sid, :now)",
        {"cid": conv_id, "content": content, "sid": sender_staff_id, "now": now_str()},
    )


