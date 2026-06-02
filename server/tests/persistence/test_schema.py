"""Persistence: schema.py — metadata 表定义 / 索引 / now_str / CHECK 约束。

策略：
- now_str: 纯函数，校验格式 + UTC + 单调（一秒内两次调用差 ≤ 1s）。
- metadata 表/列/索引存在性：通过 sqlalchemy MetaData 读 schema 对象本身（无需建库）。
- create_all 后查 sqlite_master 验证索引实际落库。
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from ai_engine.persistence import schema
from ai_engine.persistence.db import get_conn, init_db
from ai_engine.persistence.schema import metadata, now_str


class TestNowStr:
    """now_str: UTC, "YYYY-MM-DD HH:MM:SS"，定宽 19 字符（字典序==时间序）。"""

    def test_returns_iso_like_format(self) -> None:
        s = now_str()
        # 应可被 fromisoformat 解析
        assert datetime.fromisoformat(s)
        assert len(s) == 19  # "YYYY-MM-DD HH:MM:SS"
        assert s[4] == "-" and s[7] == "-" and s[10] == " " and s[13] == ":" and s[16] == ":"

    def test_is_utc_aware_when_parsed(self) -> None:
        """now_str 写的是不带时区的 UTC，与当前 UTC 不应偏差 > 2s。"""
        s = now_str()
        parsed = datetime.fromisoformat(s).replace(tzinfo=UTC)
        diff = abs((datetime.now(UTC) - parsed).total_seconds())
        assert diff < 2.0

    def test_lex_order_matches_time_order(self) -> None:
        """同一进程内多次调用，字符串序应 == 时间序。"""
        a = now_str()
        b = now_str()
        assert a <= b


class TestMetadataTables:
    """metadata 注册的表 / 关键列存在性（纯静态检查，不建库）。"""

    @pytest.mark.parametrize(
        "table_name",
        [
            "conversations",
            "messages",
            "staff",
            "tool_audits",
            "attachments",
            "tickets",
            "staff_actions",
            "ticket_events",
            "message_feedback",
            "sla_policies",
            "agent_ratings",
            "staff_groups",
            "staff_presence",
            "staff_shifts",
            "role_permissions",
            "conversation_client_info",
            "pending_timeout_pushes",
            "daily_token_usage_by_model",
        ],
    )
    def test_table_registered(self, table_name: str) -> None:
        assert table_name in metadata.tables

    def test_conversations_columns(self) -> None:
        cols = {c.name for c in metadata.tables["conversations"].columns}
        # 关键列必须在（业务高频读）
        assert {"id", "user_type", "subject_id", "mode", "assigned_staff_id",
                "assigned_at", "archived", "needs_review", "created_at"} <= cols

    def test_messages_columns(self) -> None:
        cols = {c.name for c in metadata.tables["messages"].columns}
        assert {"id", "conversation_id", "role", "content", "sender_staff_id",
                "status", "error_code", "client_message_id", "topic_verdict",
                "prompt_version", "created_at"} <= cols

    def test_user_type_check_constraint(self) -> None:
        """conversations 上有 user_type IN ('c','b','g') 的 CHECK。"""
        constraints = metadata.tables["conversations"].constraints
        ck_names = {c.name for c in constraints if c.name}
        assert "ck_conversations_user_type" in ck_names

    def test_feedback_rating_check(self) -> None:
        ck_names = {c.name for c in metadata.tables["message_feedback"].constraints if c.name}
        assert "ck_feedback_rating" in ck_names

    def test_agent_rating_range_check(self) -> None:
        ck_names = {c.name for c in metadata.tables["agent_ratings"].constraints if c.name}
        assert "ck_agent_rating_range" in ck_names

    def test_staff_role_check(self) -> None:
        ck_names = {c.name for c in metadata.tables["staff"].constraints if c.name}
        assert "ck_staff_role" in ck_names


class TestIndexesInDB:
    """create_all 后索引在 sqlite_master 中存在。"""

    async def test_conversation_subject_index(self, temp_db_url: str) -> None:
        await init_db()
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='conversations'")
            )
            idx = {row[0] for row in res.fetchall()}
        assert "idx_conv_subject" in idx

    async def test_message_client_index(self, temp_db_url: str) -> None:
        await init_db()
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'")
            )
            idx = {row[0] for row in res.fetchall()}
        assert "idx_msg_client" in idx

    async def test_staff_groups_unique_name_index(self, temp_db_url: str) -> None:
        await init_db()
        async with get_conn() as conn:
            res = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='staff_groups'")
            )
            idx = {row[0] for row in res.fetchall()}
        assert "ux_staff_group_name" in idx


class TestSchemaModuleExports:
    def test_metadata_exported(self) -> None:
        assert schema.metadata is metadata

    def test_now_str_exported(self) -> None:
        assert callable(schema.now_str)
