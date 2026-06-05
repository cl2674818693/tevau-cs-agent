import asyncio
import base64
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from ai_engine.agent import topic_classifier
from ai_engine.agent.conversation_compactor import compact_conversation
from ai_engine.agent.cost_guard import CostGuard
from ai_engine.agent.tool_router import _result_count, dispatch
from ai_engine.agent.tools import (  # noqa: F401  import 即注册工具
    base,  # 触发工具注册
    create_ticket,
    lookup_api_doc,
    lookup_error_code,
    query_balance,
    query_bu_card,
    query_bu_order,
    query_bu_request_log,
    query_bu_user,
    query_card,
    query_card_authorization,
    query_card_jit_decision,
    query_card_ledger,
    query_card_trans_error,
    query_kyc,
    query_transaction,
    query_user,
    read_file,
    search_code,
)
from ai_engine.config import settings
from ai_engine.governance.conversation_limits import should_compact
from ai_engine.governance.token_budget import check_and_record
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.integrations.anthropic_client import build_messages_request
from ai_engine.integrations.redact import scan_and_redact_text
from ai_engine.observability import metrics
from ai_engine.persistence.conversations import (
    append_message,
    append_user_turn,
    finalize_turn,
    get_conversation,
    list_messages,
    message_content_text,
    set_inferred_locale,
    set_turn_verdict,
)
from ai_engine.prompts.loader import build_system_blocks, read_prompt
from ai_engine.prompts.registry import model_for, pick_version
from ai_engine.storage.object_store import get_object_store

from ai_engine.i18n import t as _t

logger = logging.getLogger(__name__)


def _failsoft_text(ui_locale: str | None) -> str:
    """回合内 LLM/工具失败时对用户的兜底文案（不外泄内部错误细节），按 ui_locale 选语言。"""
    return _t("error.failsoft", ui_locale)


def _block_to_dict(b: object) -> dict[str, Any]:
    """把 anthropic 返回的 block (object 或 dict) 都规整为 dict。"""
    if isinstance(b, dict):
        return b
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": getattr(b, "text", "")}
    if t == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(b, "id", ""),
            "name": getattr(b, "name", ""),
            "input": getattr(b, "input", {}),
        }
    return {"type": t or "unknown"}


def _record_llm(resp: object, model: str) -> None:
    metrics.llm_calls.labels(model=model).inc()
    in_tok, out_tok = _usage(resp)
    if in_tok:
        metrics.llm_tokens.labels(model=model, kind="input").inc(in_tok)
    if out_tok:
        metrics.llm_tokens.labels(model=model, kind="output").inc(out_tok)


def _usage(resp: object) -> tuple[int, int]:
    """从响应里取 (input_tokens, output_tokens)，缺失/非数字按 0 计。"""
    u = getattr(resp, "usage", None)

    def _int(name: str) -> int:
        v = getattr(u, name, 0)
        return v if isinstance(v, int) else 0

    return _int("input_tokens"), _int("output_tokens")


async def _budget_gate(
    resp: object,
    user_type: str,
    subject_id: str,
    warned: bool,
    model: str | None = None,
    ui_locale: str | None = None,
) -> tuple[bool, dict[str, Any] | None, bool]:
    """记账并裁决。返回 (是否终止本轮, 给前端的 system 事件 or None, 更新后的 warned)。

    M2: model 可选，落到 daily_token_usage.model 列（成本大盘按模型聚合）。
    ui_locale 用于本地化"额度用完"/"80%"提示文案。
    """
    in_tok, out_tok = _usage(resp)
    allowed, info = await check_and_record(user_type, subject_id, in_tok, out_tok, model=model)
    if not allowed:
        return (
            True,
            {"type": "system", "text": _t("warning.budget_exhausted", ui_locale)},
            warned,
        )
    if info.get("warn") and not warned:
        return False, {"type": "system", "text": _t("warning.budget_80", ui_locale)}, True
    return False, None, warned


def _collect_blocks(resp: object) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """规整本轮 assistant 内容，返回 (assistant_blocks, tool_calls, texts)。"""
    assistant_blocks: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    texts: list[str] = []
    for b in (_block_to_dict(x) for x in getattr(resp, "content", [])):
        if b["type"] == "text":
            assistant_blocks.append(b)
            texts.append(b["text"])
        elif b["type"] == "tool_use":
            assistant_blocks.append(b)
            tool_calls.append(b)
    return assistant_blocks, tool_calls, texts


async def _maybe_compact(
    conversation_id: int,
    ui_locale: str | None = None,
) -> tuple[int, dict[str, Any] | None, list[dict[str, Any]]]:
    """超限则总结老会话、开新会话。返回 (会话id, 给前端的 system 事件 or None, 预置 messages)。

    fail-soft：should_compact/compact_conversation 抛错时记 warning 并退化为"不压缩"，
    让主流程照常用现有会话继续，避免上游统计/总结服务故障拖垮整轮对话。
    ui_locale 决定"会话过长，已为您开启新对话"文案语言。
    """
    try:
        if not await should_compact(conversation_id):
            return conversation_id, None, []
        new_id = await compact_conversation(conversation_id)
        summary = next(
            (str(m["content"]) for m in await list_messages(new_id) if m["role"] == "system"), ""
        )
        event = {"type": "system", "text": _t("system.conversation_compacted", ui_locale, id=new_id)}
        seed = [{"role": "user", "content": f"[上文摘要]\n{summary}"}] if summary else []
        return new_id, event, seed
    except Exception:
        logger.warning(
            "compactor failed for conversation_id=%s, skipping compact", conversation_id, exc_info=True
        )
        return conversation_id, None, []


# 还原逻辑已下沉 persistence.message_content_text（与历史接口共用），此处保留别名兼容现有调用。
_history_text = message_content_text


async def _build_user_content(text: str, attachments: list[dict[str, Any]]) -> Any:
    """有附件时返回 [image..., text] 内容块（图片读对象存储转 base64）；无附件返回纯文本 str。"""
    if not attachments:
        return text
    blocks: list[dict[str, Any]] = []
    store = get_object_store()
    for a in attachments:
        raw = await store.get(a["object_key"])
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": a["mime"],
                    "data": base64.b64encode(raw).decode(),
                },
            }
        )
    if text:
        blocks.append({"type": "text", "text": text})
    return blocks


def _coalesce(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并相邻同 role 消息（Anthropic messages 需 user/assistant 交替）。
    仅当两侧都是纯文本 str 才拼接；含图片块(list)的消息保持独立。"""
    out: list[dict[str, Any]] = []
    for m in msgs:
        if (
            out
            and out[-1]["role"] == m["role"]
            and isinstance(out[-1]["content"], str)
            and isinstance(m["content"], str)
        ):
            out[-1]["content"] += "\n" + m["content"]
        else:
            out.append(dict(m))
    return out


async def _load_history(conv_id: int) -> list[dict[str, Any]]:
    """把已落库的会话历史还原成 Anthropic messages（多轮上下文）。
    带附件的 user 行重新读对象存储转 base64 注入（每轮重发，token 成本见 spec §12）。"""
    from ai_engine.persistence import attachments as att_dao

    att_map = await att_dao.list_for_conversation(conv_id)  # message_id -> [{id, mime}]
    msgs: list[dict[str, Any]] = []
    for m in await list_messages(conv_id):
        role = str(m["role"])
        content = str(m["content"])
        if role == "user":
            atts = (
                await att_dao.list_message_attachments(int(m["id"]))
                if int(m["id"]) in att_map
                else []
            )
            msgs.append({"role": "user", "content": await _build_user_content(content, atts)})
        elif role in ("assistant", "human_agent"):
            text = _history_text(role, content)
            if text:
                msgs.append({"role": "assistant", "content": text})
        # system（压缩摘要走 seed）/ ai_draft（未发出）跳过
    return _coalesce(msgs)


def _detect_locale(text: str) -> str | None:
    """spec §6.2：从用户消息粗判语言，供 AI 镜像回复语言。命中按 Unicode 区段优先级返回。"""
    for ch in text:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3:  # Hangul（韩）
            return "ko"
        if 0x3040 <= o <= 0x30FF:  # Hiragana/Katakana（日）
            return "ja"
        if 0x0E00 <= o <= 0x0E7F:  # Thai（泰）
            return "th"
        if 0x4E00 <= o <= 0x9FFF:  # CJK 统一表意（中）
            return "zh"
    # 无 CJK/东南亚字符：含拉丁字母按英文记，纯标点/数字不更新
    if any(c.isascii() and c.isalpha() for c in text):
        return "en"
    return None


_LOCALE_NAMES = {"zh": "中文", "en": "英文（English）", "ja": "日文（日本語）", "th": "泰文（ไทย）"}


def _locale_hint_block(locale: str) -> dict[str, str]:
    """『默认回复语言』兜底块：仅当用户本条消息无文字可镜像（纯图片/附件）时生效，
    优先级低于 reply_style 的镜像/显式规则。locale 来源：本轮检测→上轮推断→APP 界面语言。"""
    name = _LOCALE_NAMES.get(locale, locale)
    return {
        "type": "text",
        "text": (
            f"【默认回复语言】系统判断本次对话的默认语言为「{name}」。仅当用户本条消息"
            f"没有任何可识别的文字（例如只发送了图片或附件、无从镜像语言）时，用{name}回复。"
            "这只是兜底默认值，优先级低于 reply_style 的"
            "「镜像用户最新消息语言」与「用户显式指定语言」——只要用户消息含文字、"
            "或用户曾明确要求某语言，一律以 reply_style 规则为准，忽略本默认值。"
        ),
    }


async def _maybe_locale_hint(
    user_type: str, conversation_id: int, detected: str | None, ui_locale: str | None
) -> list[dict[str, str]]:
    """C 端/游客：无文字可镜像时返回要追加的『默认回复语言』块（否则空）。B 端不动其语言策略。
    兜底语言来源：本轮检测 → 上轮推断 inferred_locale → APP 界面语言 ui_locale。"""
    if user_type == "b":
        return []
    fallback = detected
    if not fallback:
        conv = await get_conversation(conversation_id)
        inferred = conv["inferred_locale"] if conv else None
        fallback = str(inferred) if inferred else ui_locale
    return [_locale_hint_block(fallback)] if fallback else []


async def run_turn(
    *,
    conversation_id: int,
    user_type: str,
    subject_id: str,
    user_message: str,
    model: str | None = None,
    client_message_id: str | None = None,
    attachment_ids: list[int] | None = None,
    ui_locale: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    # spec §8 prompt 版本化：按 subject_id 哈希分桶选版本；该版本贯穿本轮
    prompt_version = pick_version(subject_id)
    model = model or model_for(prompt_version) or settings.default_model
    system_blocks = build_system_blocks(user_type=user_type, version=prompt_version)
    tools = base.all_definitions()

    # spec §8 会话治理：超轮次/token 上限 → 总结老会话、开新会话继承结论
    conversation_id, compact_event, messages = await _maybe_compact(conversation_id, ui_locale)
    if compact_event:
        yield compact_event  # 压缩后用摘要 seed 作上下文
    else:
        # 未压缩：回放该会话已有历史，让模型看到多轮上下文
        messages = await _load_history(conversation_id)

    # 回合开始：user 行入库置 processing，承载状态机/幂等键/verdict
    turn_id = await append_user_turn(conversation_id, user_message, client_message_id)
    # 绑定本轮上传的图片附件（归属校验 + 防重复绑定在 DAO 内），并按 base64 块注入 LLM
    bound_atts: list[dict[str, Any]] = []
    if attachment_ids:
        from ai_engine.persistence import attachments as att_dao

        bound_atts = await att_dao.bind_attachments(
            turn_id, conversation_id, subject_id, attachment_ids
        )
    messages.append(
        {"role": "user", "content": await _build_user_content(user_message, bound_atts)}
    )
    # spec §6.2：按用户消息语言更新会话推断语言（None 时不覆盖，保留上轮判定）
    locale = _detect_locale(user_message)
    if locale:
        await set_inferred_locale(conversation_id, locale)
    # 纯图片/无文字消息无从镜像语言时，注入「默认回复语言」兜底块（仅 C 端/游客）
    system_blocks = [
        *system_blocks,
        *await _maybe_locale_hint(user_type, conversation_id, locale, ui_locale),
    ]

    # spec §6.4 第二层：haiku 前置话题分类（按需开启）。判定一律落库 + 计数。
    # 纯图片消息（文本为空）无可分类文本，跳过分类视为放行，交给主模型 vision 判断。
    if settings.topic_classifier_enabled and user_message.strip():
        verdict = await topic_classifier.classify(user_message)
        await set_turn_verdict(turn_id, verdict)
        metrics.topic_verdict_total.labels(verdict=verdict).inc()
        if verdict == "no":
            refusal = topic_classifier.refusal_text(user_type, ui_locale)
            await append_message(
                conversation_id,
                role="assistant",
                content=refusal,
                prompt_version=prompt_version,
            )
            await finalize_turn(turn_id, "done")
            yield {"type": "text", "text": refusal}
            return
        if verdict == "uncertain":
            system_blocks = [
                *system_blocks,
                {"type": "text", "text": topic_classifier.UNCERTAIN_HINT},
            ]

    guard = CostGuard(
        max_depth=settings.max_tool_depth, max_result_bytes=settings.max_tool_result_bytes
    )

    try:
        with metrics.active_conversations.track_inprogress():
            async for ev in _agent_loop(
                system_blocks, tools, model, messages, guard, user_type, subject_id, conversation_id, ui_locale
            ):
                yield ev
        await finalize_turn(turn_id, "done")
    except Exception:
        # fail-soft：LLM/工具异常不裸抛，标 failed + 给用户固定兜底文案
        logger.exception("agent turn failed (conversation_id=%s)", conversation_id)
        metrics.llm_turn_failures_total.inc()
        await finalize_turn(turn_id, "failed", "INTERNAL_ERROR")
        yield {"type": "error", "code": "INTERNAL_ERROR", "text": _failsoft_text(ui_locale)}


class _StreamRedactor:
    """按换行边界做流式脱敏：PII 正则不跨换行，故按整行 redact 后即可安全流出；

    行内未完成的尾段先缓冲，到流末（flush）再脱敏，避免把跨增量的 PII 切成两半漏脱。
    """

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, text: str) -> list[str]:
        self._buf += text
        out: list[str] = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            out.append(scan_and_redact_text(line + "\n"))
        return out

    def flush(self) -> str:
        rest, self._buf = self._buf, ""
        return scan_and_redact_text(rest) if rest else ""


def _is_tool_round(resp: Any, tool_calls: list[dict[str, Any]]) -> bool:
    return resp.stop_reason == "tool_use" and bool(tool_calls)


def _needs_self_check(resp: Any, self_check_done: bool, texts: list[str]) -> bool:
    """end_turn 出文本且尚未自检 → 强制一轮 self-check（spec §8.3）。"""
    return resp.stop_reason == "end_turn" and not self_check_done and bool(texts)


def _final_text_events(streamed: bool, texts: list[str]) -> list[dict[str, Any]]:
    """最终轮未实时流出时（无 self-check 的 end_turn / 无文本），一次性脱敏后发出。"""
    if streamed:
        return []
    return [{"type": "text", "text": scan_and_redact_text(t)} for t in texts]


async def _run_llm_streaming(req: dict[str, Any], live: bool) -> AsyncIterator[dict[str, Any]]:
    """跑一轮 LLM 流。live=True 时把文本增量按换行边界脱敏后实时 yield {"type":"text"}；
    最后 yield {"__final__": resp, "__streamed__": bool} 把完整消息与是否已流出回传给调用方。
    """
    redactor = _StreamRedactor()
    resp = None
    streamed = False
    # 通过模块属性引用 _ac.stream_turn，便于测试 monkeypatch
    async for chunk in _ac.stream_turn(req):
        if "final" in chunk:
            resp = chunk["final"]
            break
        if live:
            streamed = True
            for piece in redactor.feed(chunk["text_delta"]):
                yield {"type": "text", "text": piece}
    if live and streamed:
        tail = redactor.flush()
        if tail:
            yield {"type": "text", "text": tail}
    yield {"__final__": resp, "__streamed__": streamed}


async def _agent_loop(
    system_blocks: list[dict[str, str]],
    tools: list[dict[str, Any]],
    model: str,
    messages: list[dict[str, Any]],
    guard: CostGuard,
    user_type: str,
    subject_id: str,
    conversation_id: int,
    ui_locale: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    prompt_version = pick_version(subject_id)
    self_check_done = False
    warned_budget = False

    while True:
        # self-check 修订轮硬禁工具：避免 LLM 在 self-check 时补调 create_ticket，
        # 导致下一轮再输出一份"工单已建+完整结论"，造成回复重复。
        tool_choice = {"type": "none"} if self_check_done else None
        req = build_messages_request(
            system_blocks=system_blocks,
            messages=messages,
            tools=tools,
            model=model,
            tool_choice=tool_choice,
        )
        # self-check 已完成 → 本轮是最终回复，真 token 流式实时推出；否则（首轮/工具轮）先缓冲，
        # 因为首轮 end_turn 文本会被 self-check 修订，不能提前发给用户。
        live = self_check_done
        resp = None
        streamed = False
        async for item in _run_llm_streaming(req, live):
            if "__final__" in item:
                resp = item["__final__"]
                streamed = bool(item["__streamed__"])
            else:
                yield item

        _record_llm(resp, model)
        # spec §8 成本治理：每轮 LLM 返回后记账；超额拒服、80% 提醒
        stop, budget_event, warned_budget = await _budget_gate(
            resp, user_type, subject_id, warned_budget, model=model, ui_locale=ui_locale
        )
        if budget_event:
            yield budget_event
        if stop:
            return

        assistant_blocks, tool_calls_in_round, texts = _collect_blocks(resp)
        # 内存上下文照常追加（供 self-check / 后续轮引用本轮输出）
        if assistant_blocks:
            messages.append({"role": "assistant", "content": assistant_blocks})
        # self-check 前的草稿轮不落库：它 live=False 不流给用户，会被 self-check 修订后的
        # 最终轮取代；若也落库，刷新历史回放会出现「同一回复两条」（直播只流最终轮）。
        if assistant_blocks and not _needs_self_check(resp, self_check_done, texts):
            await _persist_assistant(conversation_id, assistant_blocks, prompt_version)

        if _is_tool_round(resp, tool_calls_in_round):
            async for ev in _emit_tool_round(
                texts,
                tool_calls_in_round,
                guard,
                user_type,
                subject_id,
                conversation_id,
                messages,
                texts_streamed=streamed,
            ):
                yield ev
            continue

        if _needs_self_check(resp, self_check_done, texts):
            self_check_done = True
            _inject_self_check(messages, prompt_version)
            continue

        # 未实时流出（无 self-check 的最终轮 / 无文本）：一次性流出最终文本
        for ev in _final_text_events(streamed, texts):
            yield ev
        return


async def collect_full_response(
    *,
    conversation_id: int,
    user_type: str,
    subject_id: str,
    user_message: str,
    model: str | None = None,
) -> str:
    """跑完整一轮，只收集最终文本（ai_draft 模式：不流给用户，攒成草稿）。"""
    parts: list[str] = []
    async for ev in run_turn(
        conversation_id=conversation_id,
        user_type=user_type,
        subject_id=subject_id,
        user_message=user_message,
        model=model,
    ):
        if ev["type"] == "text":
            parts.append(ev["text"])
    return "".join(parts)


async def _persist_assistant(
    conversation_id: int,
    assistant_blocks: list[dict[str, Any]],
    prompt_version: str | None = None,
) -> None:
    await append_message(
        conversation_id,
        role="assistant",
        content=json.dumps(
            [b for b in assistant_blocks if b["type"] == "text"], ensure_ascii=False
        ),
        prompt_version=prompt_version,
    )


def _inject_self_check(messages: list[dict[str, Any]], version: str) -> None:
    self_check_md = read_prompt("self_check", version=version)
    messages.append(
        {
            "role": "user",
            "content": (
                "在你给出上面这段最终回复之前，请按以下规则做一次审视：\n\n"
                f"{self_check_md}\n\n现给出修订后的回复（如无需修订则原样重复）。"
            ),
        }
    )


async def _emit_tool_round(
    texts: list[str],
    tool_calls: list[dict[str, Any]],
    guard: CostGuard,
    user_type: str,
    subject_id: str,
    conversation_id: int,
    messages: list[dict[str, Any]],
    texts_streamed: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """工具轮：仅流出工具调用事件，执行工具并把结果回灌 messages。

    历史注释提到"中间文本即时流出"——已废弃：工具轮的文本会在下一轮（含 self-check 修订轮）
    被 LLM 重新整合后再次流出，导致用户看到"完整诊断 + 完整诊断"重复内容（spec §8.3 self-check
    设计本意是修订后的内容覆盖草稿）。因此工具轮所有文本一律丢弃，等最终修订轮 live 流出一份。
    texts_streamed=True 时仅作签名兼容，不再影响行为。
    """
    _ = texts, texts_streamed  # 旧入参保留，文本已不再 yield，留作 spec §8.3 重复修复的契约说明
    for tc in tool_calls:
        yield {"type": "tool_call", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
    result_blocks, events = await _run_tools(
        tool_calls, guard, user_type, subject_id, conversation_id
    )
    for ev in events:
        yield ev
    messages.append({"role": "user", "content": result_blocks})


async def _run_tools(
    tool_calls: list[dict[str, Any]],
    guard: CostGuard,
    user_type: str,
    subject_id: str,
    conversation_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """执行本轮 tool_use，返回 (回灌给模型的 tool_result blocks, 流给前端的 tool_result 事件)。

    并发执行：LLM 同轮 emit 的多个 tool_use 之间无依赖（依赖会被 LLM 拆到下一轮再 call），
    用 asyncio.gather 并发执行。深度上限超出的 call 直接生成 error block，不进 gather。
    blocks 顺序按输入 tool_calls 顺序对齐（用 idx 索引），保证回灌给 LLM 的次序与 tool_use 一致。
    """
    # 第一遍：分配 guard 配额，决定哪些 call 真跑 / 哪些挂 over-depth 错误
    blocks: list[dict[str, Any] | None] = [None] * len(tool_calls)
    runnable: list[tuple[int, dict[str, Any]]] = []
    for i, tc in enumerate(tool_calls):
        if not guard.can_call_again():
            blocks[i] = {
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": "ERROR: 达到工具调用深度上限，请直接给出当前结论或建工单。",
                "is_error": True,
            }
            continue
        guard.note_call()
        runnable.append((i, tc))

    async def _one(idx: int, tc: dict[str, Any]) -> tuple[int, dict[str, Any], dict[str, Any]]:
        r = await dispatch(
            tool_name=tc["name"],
            params=tc["input"],
            user_type=user_type,
            subject_id=subject_id,
            conversation_id=conversation_id,
        )
        payload = json.dumps(
            r.get("data") if r["ok"] else {"error": r["error"]}, ensure_ascii=False
        )
        payload, truncated = guard.maybe_truncate(payload)
        if truncated:
            payload += "\n[TRUNCATED]"
        block = {
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": payload,
            "is_error": not r["ok"],
        }
        result_count = _result_count(r.get("data")) if r["ok"] else 0
        event = {
            "type": "tool_result",
            "id": tc["id"],
            "name": tc["name"],
            "ok": r["ok"],
            "result_count": result_count,
            "empty": result_count == 0,
        }
        return idx, block, event

    # 并发执行所有 runnable tool calls；异常以 ok=False 兜底，不让单工具拖垮整轮
    results = await asyncio.gather(
        *[_one(idx, tc) for idx, tc in runnable],
        return_exceptions=True,
    )

    events: list[dict[str, Any]] = []
    for (idx, tc), item in zip(runnable, results, strict=True):
        if isinstance(item, BaseException):
            # gather 兜底：synthesize 一个 error tool_result 保证 tool_use/tool_result 配对，
            # 否则 Anthropic API 下一轮会因 unpaired tool_use 直接 400。
            logger.warning(
                "tool dispatch raised, synthesizing error block: tool=%s id=%s err=%r",
                tc["name"], tc["id"], item,
            )
            blocks[idx] = {
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": "ERROR: 工具执行异常，已记录。",
                "is_error": True,
            }
            events.append({
                "type": "tool_result",
                "id": tc["id"],
                "name": tc["name"],
                "ok": False,
                "result_count": 0,
                "empty": True,
            })
            continue
        _idx, block, event = item
        blocks[_idx] = block
        events.append(event)

    final_blocks = [b for b in blocks if b is not None]
    return final_blocks, events
