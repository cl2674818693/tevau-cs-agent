from fastapi import APIRouter, Request
from pydantic import BaseModel

from ai_engine.auth.bu_session import resolve_identity
from ai_engine.persistence.conversations import create_conversation

router = APIRouter()


class ConversationsInitIn(BaseModel):
    resume: int | None = None  # 可选：传入则恢复历史会话；MVP-2 暂不实现


class ConversationsInitOut(BaseModel):
    conversation_id: int
    user_type: str
    display_name: str
    greeting: str
    history_url: str | None = None
    limits: dict[str, int]


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
    conv_id = await create_conversation(user_type=user_type, subject_id=subject_id)
    return ConversationsInitOut(
        conversation_id=conv_id,
        user_type=user_type,
        display_name=subject_id,  # display_name 后续接 query_user/bu 补脱敏名
        greeting=_GREETING.get(user_type, _GREETING["b"]),
        history_url=None,
        limits={"daily_token_used_pct": 0, "max_turns": 20},
    )
