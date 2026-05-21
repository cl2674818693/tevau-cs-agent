import json
from collections.abc import AsyncIterator
from typing import Any

from ai_engine.agent.conversation_compactor import compact_conversation
from ai_engine.agent.cost_guard import CostGuard
from ai_engine.agent.tool_router import dispatch
from ai_engine.agent.tools import (  # noqa: F401  import 即注册工具
    base,  # 触发工具注册
    create_ticket,
    lookup_api_doc,
    query_balance,
    query_bu_order,
    query_bu_request_log,
    query_card,
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
from ai_engine.persistence.conversations import append_message, list_messages
from ai_engine.prompts.loader import build_system_blocks, read_prompt
from ai_engine.prompts.registry import model_for, pick_version


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
    resp: object, user_type: str, subject_id: str, warned: bool
) -> tuple[bool, dict[str, Any] | None, bool]:
    """记账并裁决。返回 (是否终止本轮, 给前端的 system 事件 or None, 更新后的 warned)。"""
    in_tok, out_tok = _usage(resp)
    allowed, info = await check_and_record(user_type, subject_id, in_tok, out_tok)
    if not allowed:
        return (
            True,
            {
                "type": "system",
                "text": "您今日的 AI 服务额度已用完，请明日再试，或点'转人工'。",
            },
            warned,
        )
    if info.get("warn") and not warned:
        return False, {"type": "system", "text": "您今日 AI 服务额度已用 80%。"}, True
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
) -> tuple[int, dict[str, Any] | None, list[dict[str, Any]]]:
    """超限则总结老会话、开新会话。返回 (会话id, 给前端的 system 事件 or None, 预置 messages)。"""
    if not await should_compact(conversation_id):
        return conversation_id, None, []
    new_id = await compact_conversation(conversation_id)
    summary = next(
        (str(m["content"]) for m in await list_messages(new_id) if m["role"] == "system"), ""
    )
    event = {"type": "system", "text": f"会话过长，已为您开启新对话，conversation_id={new_id}"}
    seed = [{"role": "user", "content": f"[上文摘要]\n{summary}"}] if summary else []
    return new_id, event, seed


def _history_text(role: str, content: str) -> str:
    if role == "human_agent":
        return content
    # assistant 入库的是 json.dumps([{"type":"text","text":...}])，还原为纯文本
    try:
        blocks = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content
    if isinstance(blocks, list):
        return "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )
    return content


def _coalesce(msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并相邻同 role 消息（Anthropic messages 需 user/assistant 交替）。"""
    out: list[dict[str, Any]] = []
    for m in msgs:
        if out and out[-1]["role"] == m["role"]:
            out[-1]["content"] += "\n" + m["content"]
        else:
            out.append(dict(m))
    return out


async def _load_history(conv_id: int) -> list[dict[str, Any]]:
    """把已落库的会话历史还原成 Anthropic messages（多轮上下文）。"""
    msgs: list[dict[str, Any]] = []
    for m in await list_messages(conv_id):
        role = str(m["role"])
        content = str(m["content"])
        if role == "user":
            msgs.append({"role": "user", "content": content})
        elif role in ("assistant", "human_agent"):
            text = _history_text(role, content)
            if text:
                msgs.append({"role": "assistant", "content": text})
        # system（压缩摘要走 seed）/ ai_draft（未发出）跳过
    return _coalesce(msgs)


async def run_turn(
    *,
    conversation_id: int,
    user_type: str,
    subject_id: str,
    user_message: str,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    # spec §8 prompt 版本化：按 subject_id 哈希分桶选版本；该版本贯穿本轮
    prompt_version = pick_version(subject_id)
    model = model or model_for(prompt_version) or settings.default_model
    system_blocks = build_system_blocks(user_type=user_type, version=prompt_version)
    tools = base.all_definitions()

    # spec §8 会话治理：超轮次/token 上限 → 总结老会话、开新会话继承结论
    conversation_id, compact_event, messages = await _maybe_compact(conversation_id)
    if compact_event:
        yield compact_event  # 压缩后用摘要 seed 作上下文
    else:
        # 未压缩：回放该会话已有历史，让模型看到多轮上下文
        messages = await _load_history(conversation_id)

    messages.append({"role": "user", "content": user_message})
    await append_message(conversation_id, role="user", content=user_message)

    guard = CostGuard(
        max_depth=settings.max_tool_depth, max_result_bytes=settings.max_tool_result_bytes
    )

    with metrics.active_conversations.track_inprogress():
        async for ev in _agent_loop(
            system_blocks, tools, model, messages, guard, user_type, subject_id, conversation_id
        ):
            yield ev


async def _agent_loop(
    system_blocks: list[dict[str, str]],
    tools: list[dict[str, Any]],
    model: str,
    messages: list[dict[str, Any]],
    guard: CostGuard,
    user_type: str,
    subject_id: str,
    conversation_id: int,
) -> AsyncIterator[dict[str, Any]]:
    prompt_version = pick_version(subject_id)
    self_check_done = False
    warned_budget = False

    while True:
        req = build_messages_request(
            system_blocks=system_blocks, messages=messages, tools=tools, model=model
        )
        # 通过模块属性引用，便于测试用 monkeypatch.setattr 替换
        resp = await _ac._client.messages.create(**req)  # 非流式骨架，MVP-3 换 stream
        _record_llm(resp, model)

        # spec §8 成本治理：每轮 LLM 返回后记账；超额拒服、80% 提醒
        stop, budget_event, warned_budget = await _budget_gate(
            resp, user_type, subject_id, warned_budget
        )
        if budget_event:
            yield budget_event
        if stop:
            return

        # 累积本轮 assistant 内容（文本先不流出：可能要走 self-check 修订）
        assistant_blocks, tool_calls_in_round, texts = _collect_blocks(resp)
        await _persist_assistant(conversation_id, messages, assistant_blocks)

        if resp.stop_reason == "tool_use" and tool_calls_in_round:
            async for ev in _emit_tool_round(
                texts, tool_calls_in_round, guard, user_type, subject_id, conversation_id, messages
            ):
                yield ev
            continue

        # 最终回复轮：end_turn 后强制一轮 self-check（spec §8.3），不计工具深度
        if resp.stop_reason == "end_turn" and not self_check_done and texts:
            self_check_done = True
            _inject_self_check(messages, prompt_version)
            continue

        # self-check 后（或无文本）：流出最终文本
        for t in texts:
            yield {"type": "text", "text": scan_and_redact_text(t)}
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
    conversation_id: int, messages: list[dict[str, Any]], assistant_blocks: list[dict[str, Any]]
) -> None:
    if not assistant_blocks:
        return
    messages.append({"role": "assistant", "content": assistant_blocks})
    await append_message(
        conversation_id,
        role="assistant",
        content=json.dumps(
            [b for b in assistant_blocks if b["type"] == "text"], ensure_ascii=False
        ),
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
) -> AsyncIterator[dict[str, Any]]:
    """工具轮：中间文本即时流出 + 工具调用事件，执行工具并把结果回灌 messages。"""
    for t in texts:
        yield {"type": "text", "text": scan_and_redact_text(t)}
    for tc in tool_calls:
        yield {"type": "tool_call", "name": tc["name"], "input": tc["input"]}
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
    """执行本轮 tool_use，返回 (回灌给模型的 tool_result blocks, 流给前端的 tool_result 事件)。"""
    blocks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for tc in tool_calls:
        if not guard.can_call_again():
            blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": "ERROR: 达到工具调用深度上限，请直接给出当前结论或建工单。",
                    "is_error": True,
                }
            )
            continue
        guard.note_call()
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
        blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": tc["id"],
                "content": payload,
                "is_error": not r["ok"],
            }
        )
        events.append({"type": "tool_result", "name": tc["name"], "ok": r["ok"]})
    return blocks, events
