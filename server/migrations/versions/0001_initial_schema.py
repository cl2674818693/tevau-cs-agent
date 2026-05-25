"""initial schema (与 persistence/db.py 的 SCHEMA 对齐的快照)

Revision ID: 0001
Revises:
Create Date: 2026-05-25

DDL 为 SQLite 方言（当前 prod 落 SQLite）。换 Postgres 的改造点见
docs/db-postgres-migration-eval.md。本文件是不可变快照，后续变更新增 revision。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_type TEXT NOT NULL CHECK(user_type IN ('c','b','g')),
        subject_id TEXT NOT NULL,
        inferred_locale TEXT,
        mode TEXT NOT NULL DEFAULT 'ai',
        assigned_staff_id TEXT,
        assigned_at TEXT,
        archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conv_subject ON conversations(subject_id)",
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sender_staff_id TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('agent','senior','engineer','admin')),
        password_hash TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        tool_name TEXT NOT NULL,
        params_json TEXT NOT NULL,
        result_size INTEGER NOT NULL,
        duration_ms INTEGER NOT NULL,
        rejected INTEGER NOT NULL DEFAULT 0,
        reject_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_conv ON tool_audits(conversation_id)",
    """
    CREATE TABLE IF NOT EXISTS tickets (
        external_id TEXT PRIMARY KEY,
        conversation_id INTEGER NOT NULL,
        payload_json TEXT NOT NULL,
        current_severity TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS staff_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        staff_id TEXT NOT NULL,
        action TEXT NOT NULL,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_staff_actions_staff ON staff_actions(staff_id, at)",
    """
    CREATE TABLE IF NOT EXISTS daily_token_usage (
        subject_id TEXT NOT NULL,
        user_type TEXT NOT NULL,
        date TEXT NOT NULL,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (subject_id, user_type, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ticket_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT NOT NULL,
        event TEXT NOT NULL,
        actor TEXT,
        comment TEXT,
        raw_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(external_id) REFERENCES tickets(external_id)
    )
    """,
]

_TABLES = [
    "ticket_events",
    "daily_token_usage",
    "staff_actions",
    "tickets",
    "tool_audits",
    "staff",
    "messages",
    "conversations",
]


def upgrade() -> None:
    for stmt in _STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
