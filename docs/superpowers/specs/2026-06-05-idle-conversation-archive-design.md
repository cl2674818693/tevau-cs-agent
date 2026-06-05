# 空闲会话自动归档（C 端 2 天清除）— 设计

**日期**: 2026-06-05
**作者**: caril + Claude
**状态**: 待实现

## 背景

C 端 APP 嵌入客服系统，前端持有上次会话的 `conversation_id`（本地存储），进入时调用
`POST /api/v1/conversations { resume: <id> }` 续接。后端 `get_resumable` 只校验属主和
`archived=0`，**没有任何时间过期逻辑**，导致用户两三天前的聊天记录在 APP 里再次打开
依然会续上，体验上像是"客服系统不会忘事"。

期望行为：超过 2 天不活跃的 C 端 AI 会话自动"清除"——APP 重新打开拿到新会话，看不到旧内容。

## 决策

- **清除语义**：标记 `archived=1`，**不物理删除**。C 端续接走不通自然开新会话；数据库、
  B 端工作台、审计仍可查到原记录。合规风险最小，最小改动可逆。
- **只归档 `mode='ai'` 的会话**：转人工态（`human_pending` / `human_takeover`）可能正在
  客服 follow-up 中，2 天没回不代表关闭，归档会让用户回来时接不上客服。
- **空闲判定**：`COALESCE(MAX(messages.created_at), conversations.created_at) < now - N 小时`。
  既支持有消息会话（按最后一条算），也支持空会话（开了一句没说，按创建时间兜底）。
- **触发方式**：复用现有 `sweep_loop`（`persistence/maintenance.py`），不新加循环任务。
- **窗口可配置**：`IDLE_CONVERSATION_ARCHIVE_HOURS` 默认 48，设 0 禁用该清理。

## 实现要点

### 1. 新函数 `archive_idle_conversations(hours: int) -> int`

位置：`server/src/ai_engine/persistence/maintenance.py`

```python
async def archive_idle_conversations(hours: int) -> int:
    """归档超 hours 小时无活动的 mode='ai' 会话。返回归档条数。"""
    if hours <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    # 先查 id 列表用于日志/metrics，再批量 UPDATE
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
    ids = [int(r["id"]) for r in rows]
    for cid in ids:
        await db.execute(
            "UPDATE conversations SET archived = 1 WHERE id = :id",
            {"id": cid},
        )
    logger.info("archived %d idle conversations (cutoff=%s)", len(ids), cutoff)
    return len(ids)
```

执行细节：
- 直接循环单条 `await db.execute`。每次扫描量级一般 < 100（48h 一次，新增会话节奏不高），
  无性能压力，复用现有 `db.execute` 接口，不新增 DAO 便利方法。
- 不引入新 metric。日志足以观察。

### 2. 接入 `sweep_loop`

修改 `persistence/maintenance.py` 的 `sweep_loop`：

```python
try:
    await archive_idle_conversations(settings.idle_conversation_archive_hours)
except Exception:
    logger.exception("idle conversation archive sweep failed")
```

独立 try/except，单次失败不影响其他清理任务。

### 3. 配置项

`server/src/ai_engine/config.py` 新增：

```python
idle_conversation_archive_hours: int = 48  # 0=禁用
```

ENV 名：`IDLE_CONVERSATION_ARCHIVE_HOURS`。docker-compose 生产覆写 = 48（即默认）。

### 4. 测试（`server/tests/unit/test_idle_conversation_archive.py`）

覆盖用例：
- **归档命中**：会话 mode='ai'，最后消息时间 = `now - 49h` → 归档 ✓
- **未到期不归档**：最后消息时间 = `now - 47h` → 跳过 ✓
- **空会话**：mode='ai'，无消息，created_at = `now - 49h` → 归档（COALESCE 兜底）✓
- **空会话未到期**：mode='ai'，无消息，created_at = `now - 47h` → 跳过 ✓
- **非 ai 模式不归档**：mode='human_takeover'，最后消息 = `now - 72h` → 跳过 ✓
- **已 archived 跳过**：archived=1，避免无意义重写 ✓
- **hours=0 直接返回 0**：禁用开关 ✓

**双库验证**：memory 提到 SQLite vs Postgres 类型陷阱（`query_tools_drift` /
`sqlite-vs-postgres-test-gap`）。本设计 SQL 用：
- `COALESCE` / `MAX` / `GROUP BY` / `HAVING` — 两库都支持
- 参数化 `cutoff` 是字符串，无类型歧义
- 字符串字典序比较时间（schema 已统一固定宽度）

但 `GROUP BY c.id, c.created_at` 在 Postgres 严格模式下需要 SELECT 里非聚合列都列出来，
这里只 SELECT `c.id` 但 GROUP BY 包含 `c.created_at`（HAVING 用到），写法兼容 PG。
落库后必须用真实 Postgres 跑一次（docker compose 起本地 PG）确认。

### 5. 不做的事（YAGNI）

- 不改 `get_resumable`：sweep 间隔 60s，时间窗口 48h，刚好压线的会话最多多续 60s，无需双兜底。
- 不改 `/api/v1/conversations/{conv_id}/messages` 历史 API：C 端入口是 init，没了 conv_id
  自然进不去；非 C 端入口（B 端、admin）本来就是设计上允许查历史的。
- 不改前端：init 返回的是新 conv_id，前端已有"resume 失败开新"分支自然 work。
- 不动 `mode != 'ai'` 的会话。
- 不删数据，不做物理 DELETE。

## 影响面

| 端 | 影响 |
|---|---|
| C 端 APP | 超 48h 未活动的 AI 会话自动开新，旧记录看不到（符合需求） |
| B 端客服工作台 | 无影响（列表本来就 `mode != 'ai'` 过滤） |
| Admin 后台 | 无影响（如有按 conv_id 查询入口仍可用，archived 字段可见） |
| 数据库 | 单次扫描 `O(n_conversations)`，每 60s 一次；conversations 表数据量级不大 |
| 数据合规 | 数据保留，仅打标，可逆 |

## 实施清单（待 writing-plans 细化）

1. `persistence/maintenance.py` 新增 `archive_idle_conversations`
2. `sweep_loop` 接入新函数（独立 try/except）
3. `config.py` 新增 `idle_conversation_archive_hours = 48`
4. 单测 `tests/unit/test_idle_conversation_archive.py`
5. 真实 Postgres 验证一次（`docker compose up -d --build api` 后跑 sweep 一次）
6. 验证 C 端续接：构造 48h+ 旧会话，确认 `get_resumable` 返回 None，APP 进入拿新 conv_id
