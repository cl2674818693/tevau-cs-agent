import json
from collections.abc import AsyncIterator
from typing import Any

from ai_engine.agent.cost_guard import CostGuard
from ai_engine.agent.tool_router import dispatch
from ai_engine.agent.tools import (  # noqa: F401  import 即注册工具
    base,  # 触发工具注册
    create_ticket,
    lookup_api_doc,
    query_api_call,
    query_card,
    query_user,
    read_file,
    search_code,
)
from ai_engine.config import settings
from ai_engine.integrations import anthropic_client as _ac
from ai_engine.integrations.anthropic_client import build_messages_request
from ai_engine.persistence.conversations import append_message
from ai_engine.prompts.loader import build_system_blocks


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


async def run_turn(
    *,
    conversation_id: int,
    user_type: str,
    subject_id: str,
    user_message: str,
    model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    model = model or settings.default_model
    system_blocks = build_system_blocks(user_type=user_type)
    tools = base.all_definitions()

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    await append_message(conversation_id, role="user", content=user_message)

    guard = CostGuard(
        max_depth=settings.max_tool_depth, max_result_bytes=settings.max_tool_result_bytes
    )

    while True:
        req = build_messages_request(
            system_blocks=system_blocks, messages=messages, tools=tools, model=model
        )
        # 通过模块属性引用，便于测试用 monkeypatch.setattr 替换
        resp = await _ac._client.messages.create(**req)  # 非流式骨架，MVP-3 换 stream
        blocks = [_block_to_dict(b) for b in resp.content]

        # 累积本轮 assistant 内容
        assistant_blocks: list[dict[str, Any]] = []
        tool_calls_in_round: list[dict[str, Any]] = []
        for b in blocks:
            if b["type"] == "text":
                assistant_blocks.append(b)
                yield {"type": "text", "text": b["text"]}
            elif b["type"] == "tool_use":
                assistant_blocks.append(b)
                tool_calls_in_round.append(b)
                yield {"type": "tool_call", "name": b["name"], "input": b["input"]}

        if assistant_blocks:
            messages.append({"role": "assistant", "content": assistant_blocks})
            await append_message(
                conversation_id,
                role="assistant",
                content=json.dumps(
                    [b for b in assistant_blocks if b["type"] == "text"], ensure_ascii=False
                ),
            )

        if resp.stop_reason != "tool_use" or not tool_calls_in_round:
            return  # 结束

        # 调用本轮所有 tool_use
        tool_results_block: list[dict[str, Any]] = []
        for tc in tool_calls_in_round:
            if not guard.can_call_again():
                tool_results_block.append(
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
            tool_results_block.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tc["id"],
                    "content": payload,
                    "is_error": not r["ok"],
                }
            )
            yield {"type": "tool_result", "name": tc["name"], "ok": r["ok"]}

        messages.append({"role": "user", "content": tool_results_block})
