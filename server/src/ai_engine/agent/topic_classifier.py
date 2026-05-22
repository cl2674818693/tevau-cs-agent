"""前置话题分类器（spec §6.4 第二层）：haiku 判定消息是否 Tevau 业务相关。

三态：yes（正常走主 agent）/ no（直接返回 refusal）/ uncertain（走主 agent 但注入提示）。
分类失败 fail-open 到 uncertain，避免误伤正常用户。第一层 system prompt 边界始终生效。
"""

from typing import Literal

from ai_engine.integrations import anthropic_client as _ac

Verdict = Literal["yes", "no", "uncertain"]

# spec §6.4 固定 refusal 模板：C 端中文、B 端英文（与 topic_scope.md 一致）。
REFUSAL: dict[str, str] = {
    "c": "我是 Tevau 助手，只能帮您处理账户、卡片或 Open API 相关问题。请问您需要咨询哪方面？",
    "b": (
        "I'm Tevau's support assistant. I only handle questions about your Tevau "
        "account, cards, or our Open API. What can I help you with?"
    ),
}

UNCERTAIN_HINT = (
    "用户消息可能不是 Tevau 相关，请优先判断话题是否在范围内，超范围按固定 refusal 拒答。"
)


async def classify(message: str) -> Verdict:
    try:
        word = (await _ac.classify_topic(message)).strip().lower()
    except Exception:
        return "uncertain"
    if word.startswith("no"):
        return "no"
    if word.startswith("yes"):
        return "yes"
    return "uncertain"


def refusal_text(user_type: str) -> str:
    return REFUSAL.get(user_type, REFUSAL["c"])
