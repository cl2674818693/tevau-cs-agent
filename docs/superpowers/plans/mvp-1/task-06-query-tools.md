# Task 6: query_user / query_card / query_api_call 工具（mock fixture）

> MVP-1 plan 拆分文件 — 总览见 [README.md](./README.md)，原始合并版见 [../2026-05-18-MVP-1-客服工单AI引擎.md](../2026-05-18-MVP-1-客服工单AI引擎.md)

**Files:**
- Create: `tests/fixtures/seed.sql`
- Create: `src/ai_engine/agent/tools/query_user.py`
- Create: `src/ai_engine/agent/tools/query_card.py`
- Create: `src/ai_engine/agent/tools/query_api_call.py`
- Create: `tests/test_query_tools.py`

MVP-1 阶段这三个工具读 SQLite 里的 fixture 表（在主 db 文件里增加几张以 `mock_` 前缀的表）。上线前由后端同学换成真实只读副本的连接。

- [ ] **Step 1: 写 `tests/fixtures/seed.sql`**

```sql
CREATE TABLE IF NOT EXISTS mock_users (
    user_id TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL,
    email TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS mock_cards (
    card_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    bu_id TEXT NOT NULL,
    status TEXT NOT NULL,
    lock_reason TEXT
);
CREATE TABLE IF NOT EXISTS mock_api_calls (
    uid TEXT PRIMARY KEY,
    bu_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    error_code TEXT,
    request_json TEXT,
    response_json TEXT,
    created_at TEXT
);

INSERT OR IGNORE INTO mock_users(user_id, bu_id, email, status) VALUES
  ('U1', 'BU00243780', 'a@x.com', 'active'),
  ('U2', 'BU_OTHER',   'b@x.com', 'active');

INSERT OR IGNORE INTO mock_cards(card_id, user_id, bu_id, status, lock_reason) VALUES
  ('4938750672464590', 'U1', 'BU00243780', 'locked', '风控规则 R-217 命中'),
  ('1111222233334444', 'U2', 'BU_OTHER',   'active', NULL);

INSERT OR IGNORE INTO mock_api_calls(uid, bu_id, endpoint, status_code, error_code, request_json, response_json, created_at) VALUES
  ('1765348436409', 'BU00243780', '/v2/card/bind', 500, 'DB_TIMEOUT', '{}', '{"error":"DB_TIMEOUT"}', '2026-05-18T10:00:00');
```

- [ ] **Step 2: 扩展 `tests/conftest.py` 注入 fixture**

在 `temp_db_url` fixture 后追加：

```python
@pytest.fixture
async def seeded_db(temp_db_url):
    from ai_engine.persistence.db import init_db, get_conn
    await init_db()
    from pathlib import Path
    sql = Path("tests/fixtures/seed.sql").read_text()
    async with get_conn() as conn:
        await conn.executescript(sql)
        await conn.commit()
    return temp_db_url
```

- [ ] **Step 3: 写 `tests/test_query_tools.py`**

```python
import pytest


async def test_query_user_returns_only_subject_bu(seeded_db):
    from ai_engine.agent.tools.query_user import run
    out = await run(bu_id="BU00243780", user_id="U1")
    assert out["user"]["email"] == "a@x.com"


async def test_query_user_rejects_cross_bu(seeded_db):
    from ai_engine.agent.tools.query_user import run
    out = await run(bu_id="BU00243780", user_id="U2")  # U2 属于 BU_OTHER
    assert out["user"] is None
    assert "not found" in out["note"].lower() or "not in" in out["note"].lower()


async def test_query_card_returns_lock_reason(seeded_db):
    from ai_engine.agent.tools.query_card import run
    out = await run(bu_id="BU00243780", card_id="4938750672464590")
    assert out["card"]["status"] == "locked"
    assert "R-217" in out["card"]["lock_reason"]


async def test_query_api_call_by_uid(seeded_db):
    from ai_engine.agent.tools.query_api_call import run
    out = await run(bu_id="BU00243780", uid="1765348436409")
    assert out["call"]["status_code"] == 500
    assert out["call"]["error_code"] == "DB_TIMEOUT"
```

- [ ] **Step 4: 写 `src/ai_engine/agent/tools/query_user.py`**

```python
from ai_engine.persistence.db import get_conn
from ai_engine.agent.tools.base import Tool, register


async def run(bu_id: str, user_id: str) -> dict:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT user_id, bu_id, email, status FROM mock_users WHERE user_id=? AND bu_id=?",
            (user_id, bu_id),
        )).fetchone()
    if not row:
        return {"user": None, "note": f"user {user_id} not in BU {bu_id}"}
    return {"user": dict(row)}


register(Tool(
    name="query_user",
    description="查询某个 user 的基本信息（仅限当前 BU 下的 user）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},   # router 会强制注入
            "user_id": {"type": "string"},
        },
        "required": ["user_id"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 5: 写 `src/ai_engine/agent/tools/query_card.py`**

```python
from ai_engine.persistence.db import get_conn
from ai_engine.agent.tools.base import Tool, register


async def run(bu_id: str, card_id: str) -> dict:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT card_id, user_id, status, lock_reason FROM mock_cards WHERE card_id=? AND bu_id=?",
            (card_id, bu_id),
        )).fetchone()
    if not row:
        return {"card": None, "note": f"card {card_id} not in BU {bu_id}"}
    return {"card": dict(row)}


register(Tool(
    name="query_card",
    description="查询卡片状态与锁定原因（仅限当前 BU 下）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},
            "card_id": {"type": "string"},
        },
        "required": ["card_id"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 6: 写 `src/ai_engine/agent/tools/query_api_call.py`**

```python
from ai_engine.persistence.db import get_conn
from ai_engine.agent.tools.base import Tool, register


async def run(bu_id: str, uid: str) -> dict:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT uid, endpoint, status_code, error_code, request_json, response_json, created_at "
            "FROM mock_api_calls WHERE uid=? AND bu_id=?",
            (uid, bu_id),
        )).fetchone()
    if not row:
        return {"call": None, "note": f"uid {uid} not found for BU {bu_id}"}
    return {"call": dict(row)}


register(Tool(
    name="query_api_call",
    description="按 uid（请求唯一 ID）查询一次 API 调用的日志（仅限当前 BU）。",
    input_schema={
        "type": "object",
        "properties": {
            "bu_id": {"type": "string"},
            "uid": {"type": "string"},
        },
        "required": ["uid"],
    },
    handler=run,
    requires_subject_id=True,
))
```

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_query_tools.py -v
```
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add tests/fixtures/seed.sql tests/conftest.py src/ai_engine/agent/tools/query_user.py src/ai_engine/agent/tools/query_card.py src/ai_engine/agent/tools/query_api_call.py tests/test_query_tools.py
git commit -m "feat: query_user / query_card / query_api_call 工具（mock fixture，BU 强制隔离）"
```

> **MVP-2 重构预告**：本 task 的 query_* 工具读的是 SQLite 同库的 `mock_*` 表。MVP-2 接真实 MySQL 业务库时，**每个工具的 `async with get_conn()` 都要换成对应业务库的 `aiomysql` 连接池**（`get_nexus_conn()` / `get_tevau_conn()` 等），且必须在 handler 内做敏感字段脱敏（spec §5.4）。本次 task 是接口骨架，不要为这个未来的重构提前抽象；MVP-2 时按那时的真实 schema 重写更稳。

---
