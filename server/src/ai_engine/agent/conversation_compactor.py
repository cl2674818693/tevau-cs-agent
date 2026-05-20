"""会话压缩（spec §8）：把过长会话总结成一段，开新会话继承结论。"""

from typing import cast

from ai_engine.config import settings
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.persistence.conversations import (
    archive_conversation,
    create_conversation,
    get_conversation,
    list_messages,
)
from ai_engine.persistence.db import get_conn

_SUMMARY_SYSTEM = (
    "你是会话压缩器。把下面这段客服对话提炼成一段中文摘要，"
    "保留：用户身份与诉求、已确认的关键诊断与证据、已建工单/外部单号、待办与下一步。"
    "丢弃寒暄和重复。只输出摘要正文，不要前缀。"
)


def _render_history(messages: list[dict[str, object]]) -> str:
    lines = []
    for m in messages:
        role = str(m.get("role", ""))
        content = str(m.get("content", ""))
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


async def _summarize(history: str) -> str:
    resp = await _ac._client.messages.create(
        model=settings.summary_model,
        max_tokens=1024,
        system=_SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": history}],
    )
    parts = [
        getattr(b, "text", "")
        for b in getattr(resp, "content", [])
        if getattr(b, "type", None) == "text"
    ]
    return "".join(parts).strip() or "（无可总结内容）"


async def compact_conversation(conv_id: int) -> int:
    """总结老会话、开新会话（把摘要作为第一条 system 消息注入），归档老会话。返回新 conv_id。"""
    conv = await get_conversation(conv_id)
    if conv is None:
        raise ValueError("conv not found")
    messages = await list_messages(conv_id)
    summary = await _summarize(_render_history(messages))

    new_id = await create_conversation(
        user_type=cast(str, conv["user_type"]), subject_id=cast(str, conv["subject_id"])
    )
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, 'system', ?)",
            (new_id, summary),
        )
        await conn.commit()
    await archive_conversation(conv_id)
    return new_id
