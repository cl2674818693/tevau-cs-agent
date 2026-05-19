# Task 2: SQLite 持久层（schema + 基础 DAO）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `server/src/ai_engine/persistence/__init__.py`
- Create: `server/src/ai_engine/persistence/db.py`
- Create: `server/src/ai_engine/persistence/conversations.py`
- Create: `server/src/ai_engine/persistence/audit.py`
- Create: `server/src/ai_engine/persistence/tickets.py`
- Create: `server/tests/test_persistence_schema.py`
- Create: `server/tests/conftest.py`

- [ ] **Step 1: 写 `server/tests/conftest.py`（共享 fixture）**

```python
import asyncio
import os
import pytest
import tempfile


@pytest.fixture
def temp_db_url(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DB_URL", url)
    from ai_engine.config import settings
    settings.reload()
    yield url
    os.remove(path)
```

- [ ] **Step 2: 写 `server/tests/test_persistence_schema.py`（失败测试）**

```python
import pytest


async def test_init_creates_tables(temp_db_url):
    from ai_engine.persistence.db import init_db, get_conn
    await init_db()
    async with get_conn() as conn:
        rows = await (await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()
    names = {r[0] for r in rows}
    assert {"conversations", "messages", "tool_audits", "tickets", "ticket_events"} <= names


async def test_create_and_get_conversation(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.conversations import create_conversation, get_conversation
    await init_db()
    conv_id = await create_conversation(user_type="b", subject_id="BU00243780")
    conv = await get_conversation(conv_id)
    assert conv["user_type"] == "b"
    assert conv["subject_id"] == "BU00243780"


async def test_append_and_list_messages(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.conversations import create_conversation, append_message, list_messages
    await init_db()
    conv_id = await create_conversation(user_type="b", subject_id="BU00243780")
    await append_message(conv_id, role="user", content="hi")
    await append_message(conv_id, role="assistant", content="hello")
    msgs = await list_messages(conv_id)
    assert [m["role"] for m in msgs] == ["user", "assistant"]


async def test_audit_log_tool_call(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.audit import log_tool_call, list_audits
    await init_db()
    await log_tool_call(
        conversation_id=1, tool_name="search_code",
        params={"repo": "openapi_backend", "query": "card_bind"},
        result_size=2048, duration_ms=42, rejected=False, reject_reason=None,
    )
    rows = await list_audits(conversation_id=1)
    assert len(rows) == 1 and rows[0]["tool_name"] == "search_code"


async def test_ticket_crud(temp_db_url):
    from ai_engine.persistence.db import init_db
    from ai_engine.persistence.tickets import create_ticket, get_ticket, append_ticket_event
    await init_db()
    ext_id = "AI-2026-05-18-7a3f1c"
    await create_ticket(external_id=ext_id, conversation_id=1, payload={"category": "bug"})
    await append_ticket_event(ext_id, event="assigned", actor="嘉豪", comment="ok")
    t = await get_ticket(ext_id)
    assert t["events"][-1]["event"] == "assigned"
```

- [ ] **Step 3: 跑确认失败**

```bash
pytest tests/test_persistence_schema.py -v
```
Expected: ImportError / FAIL

- [ ] **Step 4: 写 `server/src/ai_engine/persistence/__init__.py`（空文件）**

- [ ] **Step 5: 写 `server/src/ai_engine/persistence/db.py`**

```python
import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path
from ai_engine.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT NOT NULL CHECK(user_type IN ('c','b')),
    subject_id TEXT NOT NULL,
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


async def init_db():
    path = _path_from_url(settings.db_url)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


@asynccontextmanager
async def get_conn():
    path = _path_from_url(settings.db_url)
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn
```

- [ ] **Step 6: 写 `server/src/ai_engine/persistence/conversations.py`**

```python
from ai_engine.persistence.db import get_conn


async def create_conversation(user_type: str, subject_id: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO conversations(user_type, subject_id) VALUES (?, ?)",
            (user_type, subject_id),
        )
        await conn.commit()
        return cur.lastrowid


async def get_conversation(conv_id: int) -> dict:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT id, user_type, subject_id, created_at FROM conversations WHERE id=?", (conv_id,)
        )).fetchone()
    return dict(row) if row else None


async def append_message(conv_id: int, role: str, content: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, content),
        )
        await conn.commit()
        return cur.lastrowid


async def list_messages(conv_id: int) -> list[dict]:
    async with get_conn() as conn:
        rows = await (await conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id=? ORDER BY id",
            (conv_id,),
        )).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 7: 写 `server/src/ai_engine/persistence/audit.py`**

```python
import json
from ai_engine.persistence.db import get_conn


async def log_tool_call(
    conversation_id: int,
    tool_name: str,
    params: dict,
    result_size: int,
    duration_ms: int,
    rejected: bool,
    reject_reason: str | None,
) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            """INSERT INTO tool_audits
            (conversation_id, tool_name, params_json, result_size, duration_ms, rejected, reject_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, tool_name, json.dumps(params, ensure_ascii=False),
             result_size, duration_ms, 1 if rejected else 0, reject_reason),
        )
        await conn.commit()
        return cur.lastrowid


async def list_audits(conversation_id: int) -> list[dict]:
    async with get_conn() as conn:
        rows = await (await conn.execute(
            "SELECT id, tool_name, params_json, result_size, duration_ms, rejected, reject_reason, created_at "
            "FROM tool_audits WHERE conversation_id=? ORDER BY id",
            (conversation_id,),
        )).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 8: 写 `server/src/ai_engine/persistence/tickets.py`**

```python
import json
from ai_engine.persistence.db import get_conn


async def create_ticket(external_id: str, conversation_id: int, payload: dict) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO tickets(external_id, conversation_id, payload_json) VALUES (?, ?, ?)",
            (external_id, conversation_id, json.dumps(payload, ensure_ascii=False)),
        )
        await conn.commit()


async def append_ticket_event(external_id: str, event: str, actor: str | None, comment: str | None,
                              raw: dict | None = None) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO ticket_events(external_id, event, actor, comment, raw_json)
            VALUES (?, ?, ?, ?, ?)""",
            (external_id, event, actor, comment, json.dumps(raw or {}, ensure_ascii=False)),
        )
        await conn.commit()


async def get_ticket(external_id: str) -> dict | None:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT external_id, conversation_id, payload_json, created_at FROM tickets WHERE external_id=?",
            (external_id,),
        )).fetchone()
        if not row:
            return None
        evs = await (await conn.execute(
            "SELECT event, actor, comment, created_at FROM ticket_events WHERE external_id=? ORDER BY id",
            (external_id,),
        )).fetchall()
    out = dict(row)
    out["events"] = [dict(e) for e in evs]
    return out
```

- [ ] **Step 9: 跑测试确认通过**

```bash
pytest tests/test_persistence_schema.py -v
```
Expected: 5 passed

- [ ] **Step 10: Commit**

```bash
git add server/src/ai_engine/persistence server/tests/conftest.py server/tests/test_persistence_schema.py
git commit -m "feat: SQLite 持久层（对话/审计/工单 schema 与 DAO）"
```

---
