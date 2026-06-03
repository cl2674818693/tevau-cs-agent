"""前置话题分类器（spec §6.4 第二层）：haiku 判定消息是否 Tevau 业务相关。

三态：yes（正常走主 agent）/ no（直接返回 refusal）/ uncertain（走主 agent 但注入提示）。
分类失败 fail-open 到 uncertain，避免误伤正常用户。第一层 system prompt 边界始终生效。
"""

import logging
from typing import Literal

from ai_engine.i18n import t as _t
from ai_engine.integrations import anthropic_client as _ac

logger = logging.getLogger(__name__)

Verdict = Literal["yes", "no", "uncertain"]

# spec §6.4 固定 refusal 模板已 i18n 化（i18n/messages.py:refusal.c）。
# C/B 端共用同一文案（B 端 ui_locale 走 en，C 端跟随 APP 当前语言）。

UNCERTAIN_HINT = (
    "用户消息可能不是 Tevau 相关，请优先判断话题是否在范围内，超范围按固定 refusal 拒答。"
)


async def classify(message: str) -> Verdict:
    try:
        word = (await _ac.classify_topic(message)).strip().lower()
    except Exception:
        # fail-open 到 uncertain（第一层 system 边界仍生效），但记录便于排障
        logger.warning("topic classify failed, fail-open to uncertain", exc_info=True)
        return "uncertain"
    if word.startswith("no"):
        return "no"
    if word.startswith("yes"):
        return "yes"
    return "uncertain"


def refusal_text(user_type: str, ui_locale: str | None = None) -> str:
    """超范围话题拒答文案。C/B 端共享同一 i18n key（refusal.c），ui_locale 决定具体语言。
    B 端不传 ui_locale 时回退 en；C 端 webview 必带 APP 当前 language。"""
    return _t("refusal.c", ui_locale)
