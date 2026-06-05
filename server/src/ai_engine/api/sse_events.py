"""SSE 事件类型常量与 helper。对齐 spec §3.3 SSE 协议契约。

所有 SSE event 名都从这里取，避免 chat.py / runtime / 前端拼写不一致。
"""

import json
from typing import Any, Literal

# 完整事件类型清单（spec §3.3 表）
EVENT_CONVERSATION = "conversation"  # 首事件：携带 user_type / conversation_id / model
EVENT_MESSAGE_START = "message_start"  # assistant 消息开始
EVENT_CONTENT_BLOCK_DELTA = "content_block_delta"  # 文本流式增量
EVENT_TOOL_USE = "tool_use"  # AI 决定调工具
EVENT_TOOL_RESULT = "tool_result"  # 工具返回（已脱敏）
EVENT_MESSAGE_STOP = "message_stop"  # assistant 消息结束（含 stop_reason）
EVENT_TICKET_EVENT = "ticket_event"  # 工单状态推送（MVP-3 替换轮询）
EVENT_MODE_CHANGE = "mode_change"  # mode 切换（MVP-2 上线）
EVENT_HUMAN_MESSAGE = "human_message"  # 客服消息（MVP-2 上线）
EVENT_ERROR = "error"  # 错误（见错误码表）
EVENT_WARNING = "warning"  # 警告（如 80% token 阈值）
EVENT_PING = "ping"  # 心跳

# 错误码（spec §3.3 错误码表）
ErrorCode = Literal[
    "AUTH_EXPIRED",
    "RATE_LIMITED",
    "SYSTEM_BUSY",  # 新增：进程内 LLM 并发上限拒绝（Semaphore busy），前端可短退避后重试
    "TOOL_DEPTH_EXCEEDED",
    "MODEL_OVERLOADED",
    "CONVERSATION_NOT_FOUND",
    "INTERNAL_ERROR",
]

PING_INTERVAL_SECONDS = 30
CLIENT_IDLE_TIMEOUT_SECONDS = 60  # 客户端 60s 无事件视为断线，主动重连


def sse_payload(event: str, data: dict[str, Any], event_id: str | None = None) -> dict[str, str]:
    """构造 sse-starlette EventSourceResponse 期望的 dict 格式。"""
    out: dict[str, str] = {"event": event, "data": json.dumps(data, ensure_ascii=False)}
    if event_id:
        out["id"] = event_id  # 客户端用 Last-Event-ID 头携带，服务端从该 id 后补推
    return out


def error_event(code: ErrorCode, message: str, retry_after_ms: int | None = None) -> dict[str, str]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if retry_after_ms is not None:
        payload["retry_after_ms"] = retry_after_ms
    return sse_payload(EVENT_ERROR, payload)
