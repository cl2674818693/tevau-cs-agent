import json
import time
from typing import Any

from ai_engine.agent.tools import base
from ai_engine.observability import metrics
from ai_engine.persistence.audit import log_tool_call

NEEDS_CONVERSATION_ID = {"create_ticket"}


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

    # 身份注入：把会话身份强写入工具声明的 subject_field（覆盖 AI 传值）。
    # 工具内部按自身语义用该值查对应列（C 端 user_id / B 端 tenant_id / 工单 bu_id）。
    safe_params = dict(params)
    safe_params.pop("unmask", None)
    if tool.requires_subject_id:
        safe_params[tool.subject_field] = subject_id
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
