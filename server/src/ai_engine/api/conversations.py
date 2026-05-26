from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.agent.runtime import _history_text  # assistant 存的是 json blob，复用还原逻辑
from ai_engine.auth.bu_session import resolve_identity
from ai_engine.persistence.conversations import (
    create_conversation,
    get_conversation,
    get_resumable,
    list_messages,
)

router = APIRouter()

# 历史回放给用户看的角色（排除 ai_draft 草稿、system 内部）
_USER_FACING_ROLES = {"user", "assistant", "human_agent"}


class ConversationsInitIn(BaseModel):
    resume: int | None = None  # 可选：传入会话 id，属主+未归档校验通过则续接历史，否则新建


class ConversationsInitOut(BaseModel):
    conversation_id: int
    user_type: str
    display_name: str
    greeting: str
    mode: str  # 续接已转人工的会话时，前端据此初始化 UI（默认 "ai"）
    history_url: str | None = None
    limits: dict[str, int]


class HistoryMessage(BaseModel):
    role: str
    content: str


class ConversationHistoryOut(BaseModel):
    messages: list[HistoryMessage]


# 标题（前端 EmptyState 写死「你好，我是 Tevau 助手」）已报过名，
# 这里只写「按端区分」的纯介绍句，避免重复报名。
_GREETING = {
    "c": "账户、卡片、交易记录，或使用中遇到的问题，都可以直接问我。",
    "b": "可以帮你解答 Open API 接入、卡片业务、对接联调等问题。",
    "g": "未登录也能解答 API、APP 使用等通用问题；"
    "查询账户、卡片或交易记录需先登录。",
}


@router.post("/api/v1/conversations")
async def init_conversation(body: ConversationsInitIn, request: Request) -> ConversationsInitOut:
    user_type, subject_id = await resolve_identity(request)

    # resume：传入且属主校验通过且未归档 → 续接旧会话(保留历史+当前 mode)；否则新建。
    mode = "ai"
    conv_id: int | None = None
    if body.resume is not None:
        row = await get_resumable(body.resume, user_type=user_type, subject_id=subject_id)
        if row is not None:
            conv_id = int(row["id"])
            mode = str(row["mode"])
    if conv_id is None:
        conv_id = await create_conversation(user_type=user_type, subject_id=subject_id)

    return ConversationsInitOut(
        conversation_id=conv_id,
        user_type=user_type,
        display_name=subject_id,  # display_name 后续接 query_user/bu 补脱敏名
        greeting=_GREETING.get(user_type, _GREETING["b"]),
        mode=mode,
        history_url=f"/api/v1/conversations/{conv_id}/messages",
        limits={"daily_token_used_pct": 0, "max_turns": 20},
    )


@router.get("/api/v1/conversations/{conv_id}/messages")
async def get_history(conv_id: int, request: Request) -> ConversationHistoryOut:
    """会话历史回放（前端切后台被杀重载后恢复对话用）。属主校验同 messages-stream。"""
    user_type, subject_id = await resolve_identity(request)
    conv = await get_conversation(conv_id)
    if conv is None or conv["subject_id"] != subject_id or conv["user_type"] != user_type:
        raise HTTPException(403, "not your conversation")

    rows = await list_messages(conv_id)
    out: list[HistoryMessage] = []
    for r in rows:
        role = str(r["role"])
        if role not in _USER_FACING_ROLES:
            continue
        # user 行只取已完成回合，避免回放半截/失败的提问
        if role == "user" and r.get("status") not in (None, "done"):
            continue
        raw = str(r["content"])
        # user 原样透传；assistant/human_agent 走 json blob 还原
        content = raw if role == "user" else _history_text(role, raw)
        if not content:
            continue
        out.append(HistoryMessage(role=role, content=content))
    return ConversationHistoryOut(messages=out)
