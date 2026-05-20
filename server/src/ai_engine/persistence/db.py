from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from ai_engine.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT NOT NULL CHECK(user_type IN ('c','b')),
    subject_id TEXT NOT NULL,
    inferred_locale TEXT,                  -- spec 6.2: AI 镜像用户消息语言, runtime 每次回复后更新
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_subject ON conversations(subject_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
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


async def init_db() -> None:
    path = _path_from_url(settings.db_url)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


@asynccontextmanager
async def get_conn() -> AsyncIterator[aiosqlite.Connection]:
    path = _path_from_url(settings.db_url)
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
