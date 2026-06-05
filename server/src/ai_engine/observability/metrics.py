"""Prometheus 指标定义（spec §11 可观测性）。所有埋点从这里取，避免名称漂移。"""

from prometheus_client import Counter, Gauge, Histogram

# 实时态
active_conversations = Gauge("ai_engine_active_conversations", "当前活跃对话数")
human_pending = Gauge("ai_engine_human_pending", "等待人工接管的会话数")

# 工具调用
tool_calls = Counter("ai_engine_tool_calls_total", "工具调用次数", ["tool", "ok"])
tool_duration = Histogram("ai_engine_tool_duration_seconds", "工具耗时", ["tool"])

# LLM 成本
llm_tokens = Counter("ai_engine_llm_tokens_total", "LLM token 消耗", ["model", "kind"])
llm_calls = Counter("ai_engine_llm_calls_total", "LLM 调用次数", ["model"])

# 工单
tickets_created = Counter(
    "ai_engine_tickets_total", "工单创建", ["category", "severity", "user_type"]
)
ticket_resolution_seconds = Histogram(
    "ai_engine_ticket_resolution_seconds",
    "工单从创建到 resolved/closed 的耗时",
    ["category"],
    buckets=(60, 300, 900, 1800, 3600, 14400, 43200, 86400, 259200),
)

# 客服
staff_takeovers = Counter("ai_engine_staff_takeovers_total", "客服接管次数", ["staff_id"])
staff_takeover_seconds = Histogram(
    "ai_engine_staff_takeover_seconds",
    "客服单次接管时长（take→release/resolve/transfer）",
    ["staff_id"],
    buckets=(30, 60, 300, 900, 1800, 3600, 7200, 14400),
)

# 用户满意度
user_resolved_total = Counter("ai_engine_user_resolved_total", "用户标记解决", ["event"])

# 留痕与可靠性：话题判定 / 消息反馈 / 回合失败兜底 / 僵尸回合清理
topic_verdict_total = Counter("ai_engine_topic_verdict_total", "话题分类判定", ["verdict"])
message_feedback_total = Counter("ai_engine_message_feedback_total", "消息反馈", ["rating"])
llm_turn_failures_total = Counter("ai_engine_llm_turn_failures_total", "回合内 LLM 失败兜底次数")
stale_turns_reclaimed_total = Counter(
    "ai_engine_stale_turns_reclaimed_total", "超时僵尸回合被标记 failed 的数量"
)

# LLM 并发护栏
llm_inflight = Gauge("ai_engine_llm_inflight", "进行中的 LLM 调用数（含 stream + classify）")
llm_busy_rejections_total = Counter(
    "ai_engine_llm_busy_rejections_total", "因 Semaphore 满拒绝的 LLM 调用次数"
)
