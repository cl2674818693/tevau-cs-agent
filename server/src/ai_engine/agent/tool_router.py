import json
import time
from typing import Any

from ai_engine.agent.tools import base
from ai_engine.observability import metrics
from ai_engine.persistence.audit import log_tool_call

NEEDS_CONVERSATION_ID = {"create_ticket"}


def _subject_param_name(user_type: str) -> str:
    return "bu_id" if user_type == "b" else "user_id"


async def dispatch(
    *,
    tool_name: str,
    params: dict[str, object],
    user_type: str,
    subject_id: str,
    conversation_id: int,
    unmask: bool = False,
) -> dict[str, Any]:
    tool = base.get(tool_name)
    if tool is None:
        await log_tool_call(conversation_id, tool_name, params, 0, 0, True, "unknown tool")
        metrics.tool_calls.labels(tool=tool_name, ok="false").inc()
        return {"ok": False, "error": f"unknown tool: {tool_name}"}

    # 身份注入：把 subject_id 强写入对应字段，覆盖 AI 传值
    safe_params = dict(params)
    # 安全：AI 不能自助解锁脱敏，unmask 只由调用方（staff 端点）控制
    safe_params.pop("unmask", None)
    if tool.requires_subject_id:
        safe_params[_subject_param_name(user_type)] = subject_id
    # 个别工具需要 conversation_id（如 create_ticket）；统一注入
    if tool_name in NEEDS_CONVERSATION_ID:
        safe_params["conversation_id"] = conversation_id
    # spec §13.3：engineer 代查时解锁部分脱敏；仅对声明支持的工具注入
    if tool.supports_unmask and unmask:
        safe_params["unmask"] = True

    started = time.perf_counter()
    try:
        data = await tool.handler(**safe_params)
        duration_ms = int((time.perf_counter() - started) * 1000)
        payload = json.dumps(data, ensure_ascii=False)
        await log_tool_call(
            conversation_id,
            tool_name,
            safe_params,
            len(payload.encode("utf-8")),
            duration_ms,
            False,
            None,
        )
        _observe(tool_name, duration_ms, ok=True)
        return {"ok": True, "data": data}
    except ValueError as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(conversation_id, tool_name, safe_params, 0, duration_ms, True, str(e))
        _observe(tool_name, duration_ms, ok=False)
        return {"ok": False, "error": f"invalid args: {e}"}
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await log_tool_call(
            conversation_id, tool_name, safe_params, 0, duration_ms, True, f"internal: {e}"
        )
        _observe(tool_name, duration_ms, ok=False)
        return {"ok": False, "error": "internal error"}


def _observe(tool_name: str, duration_ms: int, ok: bool) -> None:
    metrics.tool_calls.labels(tool=tool_name, ok=str(ok).lower()).inc()
    metrics.tool_duration.labels(tool=tool_name).observe(duration_ms / 1000)
