# 空闲会话自动归档（C 端 48h 清除）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后台周期归档 mode='ai' 且 48h 无消息活动的会话，使 C 端 APP 重新进入时不再续接旧会话。

**Architecture:** 在现有 `sweep_loop` 中新增一个独立清扫步骤 `archive_idle_conversations`，按 `LEFT JOIN messages + COALESCE(MAX(m.created_at), c.created_at)` 算空闲时长，命中即 `UPDATE conversations SET archived=1`。不删数据；C 端 `get_resumable` 已过滤 `archived=0`，自然走新建分支；B 端工作台列表已 `mode != 'ai'` 过滤，无影响。

**Tech Stack:** Python 3.x / FastAPI / SQLAlchemy Core / asyncpg+aiosqlite / pydantic-settings / pytest-asyncio

**关键参考文件:**
- `server/src/ai_engine/persistence/maintenance.py`（新函数 + sweep_loop 接入）
- `server/src/ai_engine/persistence/conversations.py`（`get_resumable` 已天然过滤 archived）
- `server/src/ai_engine/persistence/schema.py`（`conversations` / `messages` 表结构）
- `server/src/ai_engine/config.py`（新增 config）
- `server/tests/persistence/test_maintenance_dao.py`（已有测试模式可参考；`db_ready` fixture + `temp_db_url`）

**全局约定:**
- 所有时间列用字符串 "YYYY-MM-DD HH:MM:SS"（schema 已统一）；构造测试时用 `(datetime.now(UTC) - timedelta(...)).strftime("%Y-%m-%d %H:%M:%S")`。
- 数据库默认 SQLite（测试用 `temp_db_url` fixture），生产 Postgres——SQL 必须两库都跑得通；改完后 docker compose 起 PG 跑一次实库验证。
- 提交信息中文，遵循已有风格（看 `git log --oneline` 参考）。

---

## File Structure

**修改文件:**
- `server/src/ai_engine/config.py` — 加 `idle_conversation_archive_hours: int = 48`
- `server/src/ai_engine/persistence/maintenance.py` — 新增 `archive_idle_conversations` 函数 + `sweep_loop` 接入

**新增/扩充测试:**
- `server/tests/persistence/test_maintenance_dao.py` — 新增 `TestArchiveIdleConversations` class
- `server/tests/unit/test_config.py` — 补一行默认值断言（如果 test_config 有该模式）

**不动文件:**
- `conversations.py`（`get_resumable` 行为已对）
- `staff_conversations.py`（B 端列表已 `mode != 'ai'`）
- `api/conversations.py`（history API 无需改）
- 前端任何文件

---

## Task 1: 新增配置项 `idle_conversation_archive_hours`

**Files:**
- Modify: `server/src/ai_engine/config.py:97-100`（在 `stale_sweep_interval_seconds` 后追加新字段）

- [ ] **Step 1: 编辑 `server/src/ai_engine/config.py`**

在第 99 行 `stale_sweep_interval_seconds: int = 60  # 后台清理扫描间隔；<=0 关闭后台任务` 之后插入：

```python
    # C 端空闲会话归档窗口（小时）。超过该时长无消息活动的 mode='ai' 会话
    # 会被 sweep_loop 标记 archived=1，APP 重新打开时 get_resumable 拿不到旧会话。
    # 0 = 禁用该清理。
    idle_conversation_archive_hours: int = 48
```

不补 `test_config.py` 断言：现有 test_config 不覆盖每个 field 的默认值断言模式，单独为此 field 加一行不符合既有惯例。

- [ ] **Step 2: 跑一次现有 config 测试，确认无回归**

Run: `cd server && pytest tests/unit/test_config.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add server/src/ai_engine/config.py
git commit -m "feat(config): 新增 idle_conversation_archive_hours 默认 48"
```

---

## Task 2: 实现 `archive_idle_conversations` —— 失败测试先行

**Files:**
- Modify: `server/tests/persistence/test_maintenance_dao.py`（在文件末尾新增 `TestArchiveIdleConversations` class）
- Modify: `server/src/ai_engine/persistence/maintenance.py`（新增函数）

### Step 1: 在 `test_maintenance_dao.py` 末尾追加失败测试

- [ ] **Step 1.1: 写测试**

在 `server/tests/persistence/test_maintenance_dao.py` 文件最末尾追加（确保和现有 `TestReclaimStaleTurns` 同级缩进、用同一个 `db_ready` fixture）：

```python
class TestArchiveIdleConversations:
    async def test_archives_ai_conversation_with_old_last_message(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        # 直接落一条 user 行作为"最后消息"，时间在 49 小时前
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 1
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 1

    async def test_keeps_recent_ai_conversation(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        recent = (datetime.now(UTC) - timedelta(hours=47)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": recent},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_archives_empty_conversation_by_created_at(self, db_ready) -> None:
        # 空会话（没有任何消息）：按 conversations.created_at 兜底判定
        cid = await conv.create_conversation("c", "U2")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 1

    async def test_keeps_recent_empty_conversation(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U2")
        # create_conversation 用 now_str()，默认就是当前时间 → 不该归档
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0

    async def test_does_not_archive_non_ai_mode(self, db_ready) -> None:
        # 转人工态会话即便很久没消息也不归档（客服可能仍在 follow-up）
        cid = await conv.create_conversation("c", "U3")
        await execute(
            "UPDATE conversations SET mode='human_takeover' WHERE id=:id", {"id": cid}
        )
        old = (datetime.now(UTC) - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_skips_already_archived(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U4")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        await execute("UPDATE conversations SET archived=1 WHERE id=:id", {"id": cid})
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0  # 已 archived 不再纳入

    async def test_hours_zero_disables(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U5")
        old = (datetime.now(UTC) - timedelta(hours=999)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=0)
        assert n == 0
```

- [ ] **Step 1.2: 跑测试，确认全部 FAIL（函数未定义）**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py::TestArchiveIdleConversations -v`
Expected: 7 个测试全部失败，错误信息含 `AttributeError: module 'ai_engine.persistence.maintenance' has no attribute 'archive_idle_conversations'`

### Step 2: 实现函数让测试通过

- [ ] **Step 2.1: 编辑 `server/src/ai_engine/persistence/maintenance.py`**

在 `reclaim_stale_turns` 函数（约 38 行结束处）之后、`push_pending_takeover_timeouts` 之前插入：

```python
async def archive_idle_conversations(hours: int) -> int:
    """归档 mode='ai' 且空闲超 hours 小时的会话，返回归档条数。

    空闲判定：COALESCE(MAX(messages.created_at), conversations.created_at) < cutoff，
    即按"最后一条消息时间"算；空会话用 conversations.created_at 兜底。
    只动 mode='ai'：转人工态(human_pending/human_takeover)可能仍在客服 follow-up 中，
    归档会让 C 端用户回来时接不上原客服。hours<=0 时直接返回 0（开关禁用）。
    """
    if hours <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.fetch_all(
        "SELECT c.id FROM conversations c "
        "LEFT JOIN messages m ON m.conversation_id = c.id "
        "WHERE COALESCE(c.archived, 0) = 0 AND c.mode = 'ai' "
        "GROUP BY c.id, c.created_at "
        "HAVING COALESCE(MAX(m.created_at), c.created_at) < :cutoff",
        {"cutoff": cutoff},
    )
    if not rows:
        return 0
    for r in rows:
        await db.execute(
            "UPDATE conversations SET archived = 1 WHERE id = :id",
            {"id": int(r["id"])},
        )
    logger.info("archived %d idle conversations (cutoff=%s)", len(rows), cutoff)
    return len(rows)
```

- [ ] **Step 2.2: 跑测试，确认 PASS**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py::TestArchiveIdleConversations -v`
Expected: 7 个测试全部 PASS

- [ ] **Step 2.3: 跑整个 maintenance 测试文件，确认现有测试无回归**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py -v`
Expected: 全部 PASS

- [ ] **Step 2.4: 提交**

```bash
git add server/src/ai_engine/persistence/maintenance.py server/tests/persistence/test_maintenance_dao.py
git commit -m "feat(maintenance): archive_idle_conversations 归档 48h 空闲 AI 会话"
```

---

## Task 3: 接入 `sweep_loop` —— 后台周期触发

**Files:**
- Modify: `server/src/ai_engine/persistence/maintenance.py:101-115`（`sweep_loop` 函数体内追加一步）
- Modify: `server/tests/persistence/test_maintenance_dao.py`（追加 sweep_loop 调用归档的测试）

### Step 1: 测试先行 —— sweep_loop 一次迭代会调用 archive

- [ ] **Step 1.1: 写测试（追加到 `TestArchiveIdleConversations` 类下方，文件末尾）**

```python
class TestSweepLoopArchives:
    async def test_sweep_loop_invokes_archive_once(
        self, db_ready, monkeypatch
    ) -> None:
        """sweep_loop 单次迭代会调用 archive_idle_conversations 一次。"""
        from ai_engine.config import settings

        # 把 interval 调小到几乎立即结束循环
        monkeypatch.setattr(settings, "stale_sweep_interval_seconds", 60)
        monkeypatch.setattr(settings, "idle_conversation_archive_hours", 48)

        calls: list[int] = []

        async def _fake_archive(hours: int) -> int:
            calls.append(hours)
            # 抛出取消让 sweep_loop 退出（避免无限循环 sleep 60s）
            raise asyncio.CancelledError

        monkeypatch.setattr(maintenance, "archive_idle_conversations", _fake_archive)

        # 让 reclaim / push 不干扰
        async def _noop_reclaim(*_a, **_k) -> int:
            return 0

        async def _noop_push() -> int:
            return 0

        monkeypatch.setattr(maintenance, "reclaim_stale_turns", _noop_reclaim)
        monkeypatch.setattr(maintenance, "push_pending_takeover_timeouts", _noop_push)

        with pytest.raises(asyncio.CancelledError):
            await maintenance.sweep_loop()
        assert calls == [48]
```

- [ ] **Step 1.2: 跑测试，确认 FAIL（sweep_loop 还没调归档）**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py::TestSweepLoopArchives -v`
Expected: FAIL，`assert calls == [48]` → 实际 `calls == []`

### Step 2: 在 sweep_loop 中接入

- [ ] **Step 2.1: 编辑 `server/src/ai_engine/persistence/maintenance.py` 的 `sweep_loop`**

把现有：

```python
async def sweep_loop() -> None:
    """后台周期清理 + 转人工超时推送。interval<=0 时立即退出（关闭）。"""
    interval = settings.stale_sweep_interval_seconds
    if interval <= 0:
        return
    while True:
        try:
            await reclaim_stale_turns(settings.stale_turn_timeout_seconds)
        except Exception:
            logger.exception("stale sweep iteration failed")
        try:
            await push_pending_takeover_timeouts()
        except Exception:
            logger.exception("pending takeover timeout sweep failed")
        await asyncio.sleep(interval)
```

改为：

```python
async def sweep_loop() -> None:
    """后台周期清理 + 转人工超时推送 + 空闲会话归档。interval<=0 时立即退出（关闭）。"""
    interval = settings.stale_sweep_interval_seconds
    if interval <= 0:
        return
    while True:
        try:
            await reclaim_stale_turns(settings.stale_turn_timeout_seconds)
        except Exception:
            logger.exception("stale sweep iteration failed")
        try:
            await push_pending_takeover_timeouts()
        except Exception:
            logger.exception("pending takeover timeout sweep failed")
        try:
            await archive_idle_conversations(settings.idle_conversation_archive_hours)
        except Exception:
            logger.exception("idle conversation archive sweep failed")
        await asyncio.sleep(interval)
```

- [ ] **Step 2.2: 跑测试，确认 PASS**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py::TestSweepLoopArchives -v`
Expected: PASS

- [ ] **Step 2.3: 跑整个 maintenance 文件，无回归**

Run: `cd server && pytest tests/persistence/test_maintenance_dao.py -v`
Expected: 全部 PASS（原有 + 7 个 archive + 1 个 sweep_loop）

- [ ] **Step 2.4: 提交**

```bash
git add server/src/ai_engine/persistence/maintenance.py server/tests/persistence/test_maintenance_dao.py
git commit -m "feat(maintenance): sweep_loop 接入空闲会话归档"
```

---

## Task 4: 全量回归 + 真实 Postgres 验证

**Files:** 无代码改动；仅运行验证。

- [ ] **Step 1: 跑 server 整体测试套件（SQLite 跑测）**

Run: `cd server && pytest tests/ -x -q`
Expected: 全部 PASS。如有 fail，必须先排查（很可能是误改了 sweep_loop 的循环出口）。

- [ ] **Step 2: 起本地 Postgres 后端**

Run: `docker compose up -d --build api`
Expected: api 容器启动成功；查看日志确认无启动错误：
```bash
docker compose logs api --tail=50
```
日志里应看到 `idle conversation archive sweep failed` **不出现**（无失败）+ `archived 0 idle conversations (cutoff=...)` 类似行（每 60s 一次；可能 archived=0 即第一次没命中）。

- [ ] **Step 3: 真实 PG 上手动验一次归档命中**

构造一个 48h+ 的会话，直接调归档函数验证（不走 sweep_loop 等 60s）：

```bash
docker compose exec api python -c "
import asyncio
from datetime import UTC, datetime, timedelta
from ai_engine.persistence import maintenance, conversations as conv
from ai_engine.persistence.db import execute, fetch_one, init_db

async def main():
    await init_db()
    cid = await conv.create_conversation('c', 'VERIFY_USER')
    old = (datetime.now(UTC) - timedelta(hours=49)).strftime('%Y-%m-%d %H:%M:%S')
    await execute(
        \"INSERT INTO messages(conversation_id, role, content, status, created_at) \"
        \"VALUES (:cid, 'user', 'hi', 'done', :t)\",
        {'cid': cid, 't': old},
    )
    n = await maintenance.archive_idle_conversations(hours=48)
    row = await fetch_one('SELECT archived FROM conversations WHERE id=:id', {'id': cid})
    print(f'archived_count={n} archived_flag={row[\"archived\"]}')
    assert n == 1 and row['archived'] == 1
    await execute('DELETE FROM messages WHERE conversation_id=:cid', {'cid': cid})
    await execute('DELETE FROM conversations WHERE id=:cid', {'cid': cid})

asyncio.run(main())
"
```

Expected: 标准输出 `archived_count=1 archived_flag=1`；脚本无 traceback。

- [ ] **Step 4: 端到端 —— `get_resumable` 对 archived 会话返回 None**

```bash
docker compose exec api python -c "
import asyncio
from datetime import UTC, datetime, timedelta
from ai_engine.persistence import maintenance, conversations as conv
from ai_engine.persistence.db import execute, init_db

async def main():
    await init_db()
    cid = await conv.create_conversation('c', 'VERIFY_RESUME')
    old = (datetime.now(UTC) - timedelta(hours=49)).strftime('%Y-%m-%d %H:%M:%S')
    await execute(
        \"INSERT INTO messages(conversation_id, role, content, status, created_at) \"
        \"VALUES (:cid, 'user', 'hi', 'done', :t)\",
        {'cid': cid, 't': old},
    )
    # 归档前应能 resume
    before = await conv.get_resumable(cid, user_type='c', subject_id='VERIFY_RESUME')
    assert before is not None, 'resumable before archive failed'
    # 归档
    await maintenance.archive_idle_conversations(hours=48)
    # 归档后 resume 应返回 None（C 端 APP 进入会拿到新 conv）
    after = await conv.get_resumable(cid, user_type='c', subject_id='VERIFY_RESUME')
    assert after is None, f'expected None after archive, got {after}'
    print('e2e OK')
    await execute('DELETE FROM messages WHERE conversation_id=:cid', {'cid': cid})
    await execute('DELETE FROM conversations WHERE id=:cid', {'cid': cid})

asyncio.run(main())
"
```

Expected: 标准输出 `e2e OK`；无 traceback。

- [ ] **Step 5: 端到端 —— B 端工作台列表不受影响**

回归校验：归档一个 mode='ai' 会话后，B 端 `list_for_staff(filter_status='all')` 仍按 `mode != 'ai'` 过滤，本来就不会列出 ai 态会话，archived 字段不影响这个查询。无需新增脚本；阅读 `staff_conversations.py` / `conversations.py:list_for_staff` 确认 SQL 没引用 archived 即可。

- [ ] **Step 6: 无需 commit（本任务纯验证）**

如果 Step 1-5 全过：直接进入完工汇报。如果任一 step 失败：定位问题、回退到对应 Task 修复。

---

## 验收清单

完工时应满足：

- [ ] `pytest server/tests/` 全绿
- [ ] `docker compose up -d --build api` 启动成功，无 sweep 报错
- [ ] Postgres 实库验证：`archive_idle_conversations` 命中正确
- [ ] `get_resumable` 对归档会话返回 None
- [ ] B 端工作台无影响（人工核查 SQL）
- [ ] 3 个 commit 入库：config / 实现+单测 / sweep_loop 接入

## 不在本计划范围内（YAGNI 边界）

- 不改前端
- 不动 `get_resumable`（双兜底）
- 不动 history API
- 不删数据（物理 DELETE）
- 不动 B 端列表
- 不归档 `mode != 'ai'` 的会话
- 不新增 Prometheus metric（日志足够观察；后续如要加，单独需求）
