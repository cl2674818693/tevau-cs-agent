import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from ai_engine.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT NOT NULL CHECK(user_type IN ('c','b','g')),
    subject_id TEXT NOT NULL,
    inferred_locale TEXT,                  -- spec 6.2: AI 镜像用户消息语言, runtime 每次回复后更新
    mode TEXT NOT NULL DEFAULT 'ai',       -- spec 13.2: ai/human_pending/human_takeover/ai_draft
    assigned_staff_id TEXT,                -- 当前接管客服
    assigned_at TEXT,
    archived INTEGER NOT NULL DEFAULT 0,   -- spec §8: 会话过长被总结+开新会话后置 1
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_subject ON conversations(subject_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,                    -- user / assistant / human_agent / system
    content TEXT NOT NULL,
    sender_staff_id TEXT,                  -- 仅 role=human_agent 填
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('agent','senior','engineer','admin')),
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
);
CREATE INDEX IF NOT EXISTS idx_audit_conv ON tool_audits(conversation_id);

CREATE TABLE IF NOT EXISTS tickets (
    external_id TEXT PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    current_severity TEXT,                 -- spec 7.2: 受理人可覆盖 severity, 存最新值
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    staff_id TEXT NOT NULL,
    action TEXT NOT NULL,                  -- take/release/transfer_out/transfer_in/resolved
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_staff_actions_staff ON staff_actions(staff_id, at);

CREATE TABLE IF NOT EXISTS daily_token_usage (
    subject_id TEXT NOT NULL,              -- bu_id 或 user_id
    user_type TEXT NOT NULL,
    date TEXT NOT NULL,                    -- YYYY-MM-DD
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject_id, user_type, date)
);

CREATE TABLE IF NOT EXISTS ticket_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT NOT NULL,
    event TEXT NOT NULL,
    actor TEXT,
    comment TEXT,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(external_id) REFERENCES tickets(external_id)
);
"""


def _path_from_url(url: str) -> str:
    return url.replace("sqlite+aiosqlite:///", "", 1)


_CREATE_TABLE_RE = re.compile(r"(?is)CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(\w+)")


def _normalize_table_sql(sql: str) -> str:
    """规范化 CREATE TABLE 文本用于比对：去行注释 / IF NOT EXISTS / 折叠空白与标点空格。"""
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"(?i)\bIF\s+NOT\s+EXISTS\b", "", sql)
    sql = re.sub(r"\s+", " ", sql)
    sql = re.sub(r"\s*([(),])\s*", r"\1", sql)
    return sql.strip().lower()


def _expected_tables() -> dict[str, str]:
    """从 SCHEMA 解析 表名 -> CREATE TABLE 语句。"""
    out: dict[str, str] = {}
    for stmt in SCHEMA.split(";"):
        m = _CREATE_TABLE_RE.match(stmt.strip())
        if m:
            out[m.group(1)] = stmt.strip()
    return out


async def _rebuild_table(conn: aiosqlite.Connection, name: str, create_sql: str) -> None:
    """按期望定义重建表并迁移交集列的数据（SQLite 改不了 CHECK 约束，只能重建）。

    保留 id 等列原值，messages 等外键引用因此仍有效；表上的索引随旧表 DROP，
    由随后的 executescript(CREATE INDEX IF NOT EXISTS) 重建。
    """
    tmp = f"{name}__migrate_tmp"
    tmp_create = _CREATE_TABLE_RE.sub(
        lambda m: m.group(0).replace(m.group(1), tmp, 1), create_sql, count=1
    )
    await conn.execute(f"DROP TABLE IF EXISTS {tmp}")
    await conn.execute(tmp_create)
    old_cols = [r[1] for r in await (await conn.execute(f"PRAGMA table_info({name})")).fetchall()]
    new_cols = [r[1] for r in await (await conn.execute(f"PRAGMA table_info({tmp})")).fetchall()]
    common = [c for c in new_cols if c in old_cols]
    if common:
        cols = ",".join(common)
        # 表名/列名均来自本模块 SCHEMA 常量，非外部输入
        await conn.execute(f"INSERT INTO {tmp}({cols}) SELECT {cols} FROM {name}")  # noqa: S608
    await conn.execute(f"DROP TABLE {name}")
    await conn.execute(f"ALTER TABLE {tmp} RENAME TO {name}")


async def _migrate_drifted_tables(conn: aiosqlite.Connection) -> None:
    """检测已存在但定义与 SCHEMA 不一致的表（如旧 CHECK 约束），就地重建并保留数据。"""
    expected = _expected_tables()
    rows = await (
        await conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    ).fetchall()
    actual = {r[0]: r[1] for r in rows if r[1]}
    await conn.execute("PRAGMA foreign_keys=OFF")
    for name, exp_sql in expected.items():
        act_sql = actual.get(name)
        if act_sql is None:
            continue  # 表不存在，交给 executescript 创建
        if _normalize_table_sql(act_sql) == _normalize_table_sql(exp_sql):
            continue  # 未漂移
        await _rebuild_table(conn, name, exp_sql)


async def init_db() -> None:
    path = _path_from_url(settings.db_url)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await _migrate_drifted_tables(conn)  # 先迁移漂移表（重建被 drop 的索引交给下一步）
        await conn.executescript(SCHEMA)  # 建缺失表 + 重建索引（IF NOT EXISTS 跳过已存在）
        await conn.commit()


@asynccontextmanager
async def get_conn() -> AsyncIterator[aiosqlite.Connection]:
    path = _path_from_url(settings.db_url)
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
