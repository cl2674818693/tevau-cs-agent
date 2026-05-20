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


_GREETING = {
    "c": "您好，我是 Tevau 智能助手，有账户、卡片或使用问题都可以问我。",
    "b": "您好，我是 Tevau 智能助手，可以帮您查 Open API / 卡片业务相关问题。",
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
