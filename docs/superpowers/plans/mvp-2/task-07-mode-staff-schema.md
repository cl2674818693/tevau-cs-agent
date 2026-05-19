# Task 7: conversations 扩展 mode + 客服账号 staff 表

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `server/src/ai_engine/persistence/db.py`（加表 + ALTER）
- Create: `server/src/ai_engine/persistence/staff.py`
- Modify: `server/src/ai_engine/persistence/conversations.py`
- Create: `server/tests/test_conversation_mode.py`

- [ ] **Step 1: 改 `server/src/ai_engine/persistence/db.py`**——加 staff 表 + conversations.mode

```sql
-- 在 SCHEMA 字符串末尾追加
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('agent','senior','engineer')),
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- conversations 加 mode / assigned_staff_id（仅初始化新库时生效；既有库需手动 ALTER）
-- 见迁移脚本 scripts/migrate_v2.sql
```

并新建 `scripts/migrate_v2.sql`：

```sql
ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'ai';
ALTER TABLE conversations ADD COLUMN assigned_staff_id TEXT;
ALTER TABLE conversations ADD COLUMN assigned_at TEXT;
ALTER TABLE messages ADD COLUMN sender_staff_id TEXT;
```

> SQLite 不支持 CHECK 加在 ALTER 里，所以 mode 在应用层校验。

- [ ] **Step 2: 写 `server/src/ai_engine/persistence/staff.py`**

```python
import hashlib
import secrets
from ai_engine.persistence.db import get_conn


def hash_password(plain: str, salt: str | None = None) -> str:
    """简单 sha256+salt；生产建议 argon2 但 MVP-2 用这个够。"""
    salt = salt or secrets.token_hex(8)
    h = hashlib.sha256((salt + plain).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$", 1)
    except ValueError:
        return False
    return hash_password(plain, salt) == hashed


async def create_staff(staff_id: str, display_name: str, role: str, password: str) -> int:
    if role not in {"agent", "senior", "engineer"}:
        raise ValueError("invalid role")
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO staff(staff_id, display_name, role, password_hash) VALUES (?,?,?,?)",
            (staff_id, display_name, role, hash_password(password)),
        )
        await conn.commit()
        return cur.lastrowid


async def authenticate(staff_id: str, password: str) -> dict | None:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT staff_id, display_name, role, password_hash, active FROM staff WHERE staff_id=?",
            (staff_id,),
        )).fetchone()
    if not row or int(row["active"]) != 1:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"staff_id": row["staff_id"], "display_name": row["display_name"], "role": row["role"]}


async def get_staff(staff_id: str) -> dict | None:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT staff_id, display_name, role, active FROM staff WHERE staff_id=?",
            (staff_id,),
        )).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 3: 扩展 `server/src/ai_engine/persistence/conversations.py`**

```python
# 加几个新函数
async def set_mode(conv_id: int, mode: str, assigned_staff_id: str | None = None) -> None:
    if mode not in {"ai", "human_pending", "human_takeover", "ai_draft"}:
        raise ValueError("invalid mode")
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE conversations SET mode=?, assigned_staff_id=?, "
            "assigned_at=CASE WHEN ?=? THEN datetime('now') ELSE assigned_at END "
            "WHERE id=?",
            (mode, assigned_staff_id, mode, "human_takeover", conv_id),
        )
        await conn.commit()


async def get_mode(conv_id: int) -> tuple[str, str | None]:
    async with get_conn() as conn:
        row = await (await conn.execute(
            "SELECT mode, assigned_staff_id FROM conversations WHERE id=?",
            (conv_id,),
        )).fetchone()
    if not row:
        raise ValueError("conv not found")
    return row["mode"], row["assigned_staff_id"]


async def list_for_staff(filter_status: str = "all") -> list[dict]:
    """客服工作台列表。filter_status ∈ {human_pending, human_takeover, all}"""
    async with get_conn() as conn:
        if filter_status == "all":
            sql, params = "SELECT * FROM conversations WHERE mode != 'ai' ORDER BY id DESC LIMIT 100", ()
        else:
            sql, params = ("SELECT * FROM conversations WHERE mode=? ORDER BY id DESC LIMIT 100",
                           (filter_status,))
        rows = await (await conn.execute(sql, params)).fetchall()
    return [dict(r) for r in rows]


async def append_human_message(conv_id: int, sender_staff_id: str, content: str) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO messages(conversation_id, role, content, sender_staff_id) VALUES (?,?,?,?)",
            (conv_id, "human_agent", content, sender_staff_id),
        )
        await conn.commit()
        return cur.lastrowid
```

- [ ] **Step 4: 写 `server/tests/test_conversation_mode.py`**

```python
import pytest
from ai_engine.persistence.db import init_db


async def test_mode_default_ai(temp_db_url):
    await init_db()
    # 手动跑 migrate_v2.sql（实际部署上线前由 alembic 类工具做）
    from pathlib import Path
    from ai_engine.persistence.db import get_conn
    async with get_conn() as conn:
        for stmt in Path("scripts/migrate_v2.sql").read_text().split(";"):
            if stmt.strip():
                await conn.execute(stmt)
        await conn.commit()

    from ai_engine.persistence.conversations import create_conversation, get_mode, set_mode
    cid = await create_conversation(user_type="c", subject_id="U1")
    mode, staff = await get_mode(cid)
    assert mode == "ai"
    assert staff is None

    await set_mode(cid, "human_takeover", "S100")
    mode, staff = await get_mode(cid)
    assert mode == "human_takeover"
    assert staff == "S100"


async def test_staff_crud(temp_db_url):
    await init_db()
    from ai_engine.persistence.staff import create_staff, authenticate
    sid = await create_staff("S100", "张三", "agent", "secret123")
    assert sid

    s = await authenticate("S100", "secret123")
    assert s and s["display_name"] == "张三"
    assert await authenticate("S100", "wrong") is None
```

- [ ] **Step 5: 跑测试**

```bash
pytest tests/test_conversation_mode.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add server/src/ai_engine/persistence/db.py scripts/migrate_v2.sql server/src/ai_engine/persistence/staff.py server/src/ai_engine/persistence/conversations.py server/tests/test_conversation_mode.py
git commit -m "feat(mvp-2): conversations 加 mode/assigned_staff + staff 表 + DAO"
```

---
