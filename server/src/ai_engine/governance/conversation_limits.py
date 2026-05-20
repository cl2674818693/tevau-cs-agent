"""会话长度治理（spec §8）：轮次 / 输入 token 上限。

超限时由 runtime 触发 conversation_compactor 把历史总结成一段、开新会话继承结论。
"""

from ai_engine.persistence.conversations import count_user_turns, sum_content_chars

MAX_TURNS = 20
MAX_INPUT_TOKENS = 100_000
_CHARS_PER_TOKEN = 4  # 粗估：中英混排约 1 token ≈ 4 字符


def estimate_tokens_from_chars(chars: int) -> int:
    return chars // _CHARS_PER_TOKEN


async def should_compact(conv_id: int) -> bool:
    """该会话是否需要总结+开新会话。"""
    turns = await count_user_turns(conv_id)
    if turns >= MAX_TURNS:
        return True
    tokens = estimate_tokens_from_chars(await sum_content_chars(conv_id))
    return tokens >= MAX_INPUT_TOKENS
