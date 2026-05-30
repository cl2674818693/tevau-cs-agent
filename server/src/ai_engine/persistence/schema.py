"""自有库 schema（SQLAlchemy Core / 方言无关）。

时间列用 String 存 "YYYY-MM-DD HH:MM:SS"（UTC），由应用 now_str() 在 insert 时写入：
- 避免 PG 上 String 列用 CURRENT_TIMESTAMP 默认值的类型不兼容；
- 避免 DateTime 列在两库回写类型不一致破坏 Python 侧 fromisoformat 解析。
布尔语义列（archived/active/rejected）用 Integer 0/1，两库通用。

同一份 metadata 供 init_db（create_all）与 alembic（target_metadata 自动迁移）共用。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()


def now_str() -> str:
    """UTC 时间戳，固定宽度格式，便于字典序窗口比较与 fromisoformat 解析。"""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


conversations = Table(
    "conversations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_type", String(8), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("inferred_locale", String(32)),
    Column("mode", String(32), nullable=False, server_default="ai"),
    Column("assigned_staff_id", String(64)),
    Column("assigned_at", String(32)),
    Column("archived", Integer, nullable=False, server_default="0"),
    # 👎 反馈触发：运营据此筛出待复核会话。
    Column("needs_review", Integer, nullable=False, server_default="0"),
    Column("target_group_id", Integer),  # M3a 路由匹配后写入；null 表示无定向
    Column("created_at", String(32), nullable=False),
    CheckConstraint("user_type IN ('c','b','g')", name="ck_conversations_user_type"),
)
Index("idx_conv_subject", conversations.c.subject_id)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, ForeignKey("conversations.id"), nullable=False),
    Column("role", String(32), nullable=False),
    Column("content", Text, nullable=False),
    Column("sender_staff_id", String(64)),
    # 回合状态机：user 行 processing→done/failed；其余行恒 done。
    Column("status", String(16), nullable=False, server_default="done"),
    Column("error_code", String(32)),  # status=failed 时写入（INTERNAL_ERROR / STALE_RECLAIMED）
    Column("client_message_id", String(64)),  # 幂等键，仅 user 行写
    Column("topic_verdict", String(16)),  # 话题判定，仅 user 行写：yes/no/uncertain
    Column("prompt_version", String(16)),  # 灰度 A/B：仅 assistant 行写，本轮所用 prompt 版本
    Column("created_at", String(32), nullable=False),
)
Index("idx_msg_client", messages.c.conversation_id, messages.c.client_message_id)

staff = Table(
    "staff",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("staff_id", String(64), unique=True, nullable=False),
    Column("display_name", String(128), nullable=False),
    Column("role", String(32), nullable=False),
    Column("password_hash", String(256), nullable=False),
    Column("active", Integer, nullable=False, server_default="1"),
    Column("group_id", Integer),  # M3a 可选：所属客服组
    Column("skills", Text),  # M3a 可选：技能标签 JSON 数组字符串 ["c","b","stock"]
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "role IN ('agent','senior','engineer','admin','supervisor','manager')",
        name="ck_staff_role",
    ),
)

tool_audits = Table(
    "tool_audits",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("tool_name", String(64), nullable=False),
    Column("params_json", Text, nullable=False),
    Column("result_size", Integer, nullable=False),
    Column("duration_ms", Integer, nullable=False),
    Column("rejected", Integer, nullable=False, server_default="0"),
    Column("reject_reason", Text),
    Column("result_count", Integer),
    Column("is_empty", Integer),
    Column("subject_id", String(128)),
    Column("user_type", String(8)),
    Column("created_at", String(32), nullable=False),
)
Index("idx_audit_conv", tool_audits.c.conversation_id)

attachments = Table(
    "attachments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, ForeignKey("conversations.id"), nullable=False),
    Column("message_id", Integer, ForeignKey("messages.id")),  # 上传时 NULL，发送绑定后写入
    Column("uploader_type", String(8), nullable=False),  # c / b / staff
    Column("uploader_id", String(128), nullable=False),
    Column("object_key", Text, nullable=False),
    Column("mime", String(64), nullable=False),
    Column("byte_size", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("created_at", String(32), nullable=False),
)
Index("idx_att_conv", attachments.c.conversation_id)
Index("idx_att_msg", attachments.c.message_id)

tickets = Table(
    "tickets",
    metadata,
    Column("external_id", String(64), primary_key=True),
    Column("conversation_id", Integer, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("current_severity", String(32)),
    Column("created_at", String(32), nullable=False),
)

staff_actions = Table(
    "staff_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("staff_id", String(64), nullable=False),
    Column("action", String(32), nullable=False),
    Column("at", String(32), nullable=False),
)
Index("idx_staff_actions_staff", staff_actions.c.staff_id, staff_actions.c.at)

daily_token_usage = Table(
    "daily_token_usage",
    metadata,
    Column("subject_id", String(128), primary_key=True),
    Column("user_type", String(8), primary_key=True),
    Column("date", String(16), primary_key=True),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("model", String(32)),  # M2 加列：记录主要使用模型；主键不变（M3 拆 by-model 旁路表）
)

ticket_events = Table(
    "ticket_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("external_id", String(64), ForeignKey("tickets.external_id"), nullable=False),
    Column("event", String(32), nullable=False),
    Column("actor", String(64)),
    Column("comment", Text),
    Column("raw_json", Text, nullable=False),
    Column("created_at", String(32), nullable=False),
)

# 消息级 👍/👎 反馈（spec 留痕：采集"答了但不满意"的细粒度信号）。
# message_id 不加 FK：前端消息无真实 DB id，仅作关联记录列，避免 PG 外键违例。
message_feedback = Table(
    "message_feedback",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("message_id", Integer, nullable=False),
    Column("rating", String(8), nullable=False),
    Column("reason", Text),
    Column("subject_id", String(128), nullable=False),
    Column("user_type", String(8), nullable=False),
    Column("created_at", String(32), nullable=False),
    CheckConstraint("rating IN ('up','down')", name="ck_feedback_rating"),
)
Index("idx_feedback_conv", message_feedback.c.conversation_id)

# 灰度变更审计留痕（Task 6.1）：记录谁在何时把 rollout 从 X 改到 Y。
prompt_changes = Table(
    "prompt_changes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor", String(128), nullable=False),
    Column("old_json", Text, nullable=False),
    Column("new_json", Text, nullable=False),
    Column("created_at", String(32), nullable=False),
)

# 后台统一操作审计：所有 admin/管理后台写操作落此表（账号/SLA/工具策略...）。
admin_audit_log = Table(
    "admin_audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor", String(128), nullable=False),
    Column("action", String(64), nullable=False),
    Column("target_type", String(64)),
    Column("target_id", String(128)),
    Column("detail_json", Text),
    Column("created_at", String(32), nullable=False),
)
Index("idx_admin_audit_created", admin_audit_log.c.created_at)

# SLA 策略：接管/解决时长阈值，可按全局/user_type 设。违规为运行时计算，不落表。
sla_policies = Table(
    "sla_policies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("metric", String(32), nullable=False),  # take_time / resolve_time
    Column("threshold_seconds", Integer, nullable=False),
    Column("scope", String(32), nullable=False, server_default="all"),  # all / user_type
    Column("scope_value", String(64)),  # scope=user_type 时为 c/b/g
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "metric IN ('take_time','resolve_time')", name="ck_sla_metric"
    ),
)

# 质检评分卡模板（运营定义评分项 JSON）
qa_scorecards = Table(
    "qa_scorecards",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("items_json", Text, nullable=False),  # [{"key":"polite","label":"礼貌用语","weight":1}, ...]
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
)

# 质检记录：reviewer 对一通会话按 scorecard 打分
qa_reviews = Table(
    "qa_reviews",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("reviewer_staff_id", String(64), nullable=False),
    Column("scorecard_id", Integer, nullable=False),
    Column("score", Integer, nullable=False),  # 0-100
    Column("items_result_json", Text, nullable=False),  # {"polite":1,"accurate":0,...}
    Column("tags", String(256)),  # 逗号分隔标签：violation,excellent,needs_improvement
    Column("comment", Text),
    Column("created_at", String(32), nullable=False),
)
Index("idx_qa_reviews_conv", qa_reviews.c.conversation_id)
Index("idx_qa_reviews_reviewer", qa_reviews.c.reviewer_staff_id, qa_reviews.c.created_at)

# 用户对人工客服的满意度评分（区别于 message_feedback 是对 AI 的 👍👎）
agent_ratings = Table(
    "agent_ratings",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("conversation_id", Integer, nullable=False),
    Column("staff_id", String(64), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("user_type", String(8), nullable=False),
    Column("rating", Integer, nullable=False),  # 1-5
    Column("comment", Text),
    Column("created_at", String(32), nullable=False),
    CheckConstraint("rating BETWEEN 1 AND 5", name="ck_agent_rating_range"),
)
Index("idx_agent_ratings_staff", agent_ratings.c.staff_id, agent_ratings.c.created_at)
Index("idx_agent_ratings_conv", agent_ratings.c.conversation_id)

# AI 工具按角色的策略：是否允许 / 是否可解锁脱敏。
# (tool_name, role) 唯一；表为空时回退到代码默认（M2 平滑过渡）。
tool_policies = Table(
    "tool_policies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tool_name", String(64), nullable=False),
    Column("role", String(32), nullable=False),
    Column("allowed", Integer, nullable=False, server_default="0"),
    Column("unmask_allowed", Integer, nullable=False, server_default="0"),
    Column("updated_by", String(64)),
    Column("updated_at", String(32), nullable=False),
)
Index("ux_tool_policy_role", tool_policies.c.tool_name, tool_policies.c.role, unique=True)

# 模型单价（M2 成本大盘用）。单价存"每千 token × 10000"，避免浮点 — 展示时除以 10000。
model_pricing = Table(
    "model_pricing",
    metadata,
    Column("model", String(64), primary_key=True),
    Column("input_price_per_1k_x10000", Integer, nullable=False),
    Column("output_price_per_1k_x10000", Integer, nullable=False),
    Column("currency", String(8), nullable=False, server_default="USD"),
    Column("updated_at", String(32), nullable=False),
)

# 客服分组（M3a §5.1.b）
staff_groups = Table(
    "staff_groups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False),
    Column("description", Text),
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
)
Index("ux_staff_group_name", staff_groups.c.name, unique=True)

# 客服在线状态（M3a §5.1.c）— 心跳更新 last_seen_at；后台按 5 分钟内有心跳算 online。
staff_presence = Table(
    "staff_presence",
    metadata,
    Column("staff_id", String(64), primary_key=True),
    Column("status", String(16), nullable=False, server_default="offline"),
    Column("last_seen_at", String(32), nullable=False),
)

# 排班（M3a §5.1.c）
staff_shifts = Table(
    "staff_shifts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("staff_id", String(64), nullable=False),
    Column("start_at", String(32), nullable=False),
    Column("end_at", String(32), nullable=False),
    Column("created_at", String(32), nullable=False),
)
Index("idx_shifts_staff_time", staff_shifts.c.staff_id, staff_shifts.c.start_at)

# 会话路由规则（M3a §5.1.d）
routing_rules = Table(
    "routing_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("match_type", String(32), nullable=False),
    Column("match_value", String(256), nullable=False),
    Column("target_group_id", Integer, nullable=False),
    Column("priority", Integer, nullable=False, server_default="100"),
    Column("active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), nullable=False),
    CheckConstraint(
        "match_type IN ('user_type','scope','keyword')", name="ck_routing_match_type"
    ),
)
Index("idx_routing_priority", routing_rules.c.priority, routing_rules.c.active)
