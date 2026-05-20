from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_engine.auth.bu_session import require_bu
from ai_engine.persistence.conversations import create_conversation

router = APIRouter()


class ConversationsInitIn(BaseModel):
    resume: int | None = None  # 可选：传入则恢复历史会话；MVP-1 暂不实现


class ConversationsInitOut(BaseModel):
    conversation_id: int
    user_type: str
    display_name: str
    greeting: str
    history_url: str | None = None
    limits: dict[str, int]


@router.post("/api/v1/conversations")
async def init_conversation(
    body: ConversationsInitIn,
    bu_id: str = Depends(require_bu),
) -> ConversationsInitOut:
    # MVP-1：B 端固定 greeting；display_name 用 BU_ID（接 query_bu 后再补脱敏名）
    conv_id = await create_conversation(user_type="b", subject_id=bu_id)
    return ConversationsInitOut(
        conversation_id=conv_id,
        user_type="b",
        display_name=bu_id,
        greeting="您好，我是 Tevau 智能助手，可以帮您查 Open API / 卡片业务相关问题。",
        history_url=None,
        limits={"daily_token_used_pct": 0, "max_turns": 20},
    )
