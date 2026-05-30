from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ai_engine.auth.bu_session import resolve_identity
from ai_engine.persistence import guardrails
from ai_engine.persistence.attachments import list_for_conversation
from ai_engine.persistence.conversations import (
    create_conversation,
    get_conversation,
    get_resumable,
    list_recent_messages,
    message_content_text,
)
from ai_engine.persistence.staff import get_staff

router = APIRouter()

# 历史回放给用户看的角色（排除 ai_draft 草稿、system 内部）
_USER_FACING_ROLES = {"user", "assistant", "human_agent"}
# 单次历史回放最多返回的消息数（取最近的）。spec §8 会归档超长会话，这里再加一道硬上限。
_HISTORY_MAX_MESSAGES = 200


class ConversationsInitIn(BaseModel):
    resume: int | None = None  # 可选：传入会话 id，属主+未归档校验通过则续接历史，否则新建


class ConversationsInitOut(BaseModel):
    conversation_id: int
    user_type: str
    display_name: str
    greeting: str
    mode: str  # 续接已转人工的会话时，前端据此初始化 UI（默认 "ai"）
    staff_name: str | None = None  # 续接 human_takeover 会话时的客服署名，供前端恢复顶部显示
    history_url: str | None = None
    limits: dict[str, int]


class AttachmentOut(BaseModel):
    id: int
    mime: str


class HistoryMessage(BaseModel):
    role: str
    content: str
    attachments: list[AttachmentOut] = []


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

    # M5: 入口接 guardrails——按 subject_id 维度（blocklist）拦截
    action, reason = await guardrails.evaluate(subject_id, user_type, "")
    if action == "block":
        raise HTTPException(403, f"guardrail blocked: {reason}")

    # resume：传入且属主校验通过且未归档 → 续接旧会话(保留历史+当前 mode)；否则新建。
    mode = "ai"
    staff_name: str | None = None
    conv_id: int | None = None
    if body.resume is not None:
        row = await get_resumable(body.resume, user_type=user_type, subject_id=subject_id)
        if row is not None:
            conv_id = int(row["id"])
            mode = str(row["mode"])
            assigned = row["assigned_staff_id"]
            if assigned:  # 续接已指派客服的会话：补客服署名，恢复顶部显示
                staff = await get_staff(str(assigned))
                if staff:
                    staff_name = str(staff["display_name"])
    if conv_id is None:
        conv_id = await create_conversation(user_type=user_type, subject_id=subject_id)

    return ConversationsInitOut(
        conversation_id=conv_id,
        user_type=user_type,
        display_name=subject_id,  # display_name 后续接 query_user/bu 补脱敏名
        greeting=_GREETING.get(user_type, _GREETING["b"]),
        mode=mode,
        staff_name=staff_name,
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

    rows = await list_recent_messages(conv_id, _HISTORY_MAX_MESSAGES)
    att_map = await list_for_conversation(conv_id)  # message_id -> [{id, mime}]
    out: list[HistoryMessage] = []
    for r in rows:
        role = str(r["role"])
        if role not in _USER_FACING_ROLES:
            continue
        # user 行只取已完成回合，避免回放半截/失败的提问
        if role == "user" and r.get("status") not in (None, "done"):
            continue
        content = message_content_text(role, str(r["content"]))
        atts = att_map.get(int(r["id"]), [])
        if not content and not atts:  # 纯空消息跳过；图片消息(空文本+附件)保留
            continue
        out.append(
            HistoryMessage(
                role=role,
                content=content,
                attachments=[AttachmentOut(id=a["id"], mime=a["mime"]) for a in atts],
            )
        )
    return ConversationHistoryOut(messages=out)
