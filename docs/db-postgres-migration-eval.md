# AI engine 自有库：迁移管理现状 + SQLite→Postgres 评估

> 范围限定为 AI engine **自有业务库**（会话/消息/工单/审计/token 计量等，当前
> `DB_URL=sqlite+aiosqlite:////data/ai_engine.db`）。业务**只读**库 unlimitpay/nexus
> 走阿里云 RDS，不在本文范围。

## 一、迁移管理：现状与本轮改动

### 改动前
- schema 定义集中在 `persistence/db.py` 的 `SCHEMA` 常量。
- 演进靠 `init_db()` → `_migrate_drifted_tables()`：检测已存在表的 `CREATE TABLE`
  文本与 `SCHEMA` 是否一致，不一致就**建临时表、拷贝交集列、DROP 旧表、RENAME**。
- 风险：**就地重建丢列**。若新 `SCHEMA` 删了某列或重命名，旧列数据落在"非交集"
  直接丢失，且无版本记录、无法回滚、无法 review 单次变更。

### 本轮改动（已落地）
- 引入 **alembic**（原生 SQL 迁移模式，不依赖 ORM 模型），版本目录 `server/migrations/`。
- 初始迁移 `0001_initial_schema` = 当前 `SCHEMA` 的不可变快照。
- `migrations/env.py` 从 `settings.db_url` 读目标库，自动把 async 驱动
  （`+aiosqlite`/`+asyncpg`/`+aiomysql`）转成 alembic 用的 sync URL。
- 测试 `test_alembic_migrations.py` 保证 `alembic upgrade head` 建出的表集合 ⊇
  `SCHEMA` 声明的全部业务表（parity）。
- 修了一个 env.py 引入的真 bug：`fileConfig` 默认 `disable_existing_loggers=True`
  会在进程内跑 alembic 后静默所有 `ai_engine.*` logger，已显式置 False。

### 定位（init_db vs alembic）
- **生产**：`alembic upgrade head` 作为唯一 schema 演进入口（部署步骤里执行）。
- **测试/本地 dev**：保留 `init_db()`（建表快、被大量 fixture 依赖）。
- `_migrate_drifted_tables` 暂留作 dev/test 兜底，**生产不应再依赖它**做结构变更——
  结构变更一律新增 alembic revision。

### 用法
```bash
cd server
uv run alembic upgrade head            # 应用到最新
uv run alembic downgrade -1            # 回退一格
uv run alembic revision -m "add x col" # 新增迁移（手写 op.execute）
uv run alembic history / heads / current
```
> `env.py` 的 `target_metadata=schema.metadata`，`--autogenerate` 可用：改 schema.py
> 后自动 diff 生成迁移。

## 二、SQLite → Postgres 评估

### 为什么考虑迁移
SQLite 单文件对**自有业务数据**（会话/工单是写密集、需并发）的局限：
- **并发写**：SQLite 全库写锁，多 worker/多副本下写竞争严重（WAL 也只是缓解）。
- **水平扩展**：单文件无法多实例共享（除非走网络文件系统，不可靠）。
- **备份/容灾**：文件级备份难做到一致性快照；无 PITR。
- **运维生态**：无连接池、监控、慢查询分析等成熟工具。

### 改造点清单（按工作量）

| 项 | 现状（SQLite） | Postgres 需改 | 工作量 |
|---|---|---|---|
| 驱动 | `aiosqlite` 直连 | `asyncpg`（或 `psycopg3`） | 中 |
| 连接管理 | 每次 `aiosqlite.connect(path)` | 连接池（`asyncpg.Pool` 或 SQLAlchemy async engine） | 中 |
| 自增主键 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL` / `GENERATED ... AS IDENTITY` | 小 |
| 时间默认值 | `datetime('now')`（TEXT） | `now()` + `TIMESTAMPTZ` 列类型 | 中 |
| 布尔 | `INTEGER 0/1`（archived/active/rejected） | `BOOLEAN` | 小 |
| 占位符 | `?` | `$1,$2`（asyncpg）或保持 `?`（SQLAlchemy 抽象） | 大（散落各 SQL） |
| 类型亲和 | SQLite 弱类型 | Postgres 强类型，需校列类型 | 中 |
| `PRAGMA` | foreign_keys / table_info | 无对应；外键默认强约束 | 小 |
| 大小写/排序 | SQLite 默认 | 注意 `COLLATE`、文本比较 | 小 |

### 推荐路径：引入 SQLAlchemy Core（不上 ORM）
散落在 `persistence/*.py` 的原生 SQL + `?` 占位符是最大的迁移成本。推荐：
1. 把 persistence 层的原生 SQL 收敛到 **SQLAlchemy Core**（`text()` + 命名参数或
   table/expression API），获得方言无关的占位符与类型映射——一次改造同时支持
   SQLite（dev/test）与 Postgres（prod）。
2. alembic 已就位，迁移天然兼容；初始迁移按方言出两份 DDL 或用 SQLAlchemy 类型
   让 alembic 生成方言相关 DDL。
3. 连接层换成 SQLAlchemy async engine + pool，`get_conn()` 收敛为统一会话入口。

## 三、实施状态（已完成）

评估推荐的"SQLAlchemy Core 收敛 + Postgres 支持"已实施：

- **持久层全量改造为 SQLAlchemy Core**：`persistence/schema.py` 用 MetaData/Table 定义
  方言无关 schema；`db.py` 提供 async engine（按 url 缓存）+ `fetch_one/fetch_all/
  execute/insert_returning_id` helper，对外仍返回 dict（消费方零改动）。
- **方言无关写法**：`?`→命名参数；自增主键由 SQLAlchemy Integer pk 处理；时间列用
  String 由应用 `now_str()` 写入（避免 PG 上 DateTime 回写不一致）；窗口查询用 Python
  算 cutoff；INSERT 用 `RETURNING id`（SQLite≥3.35 与 PG 均支持）。
- **schema 演进统一走 alembic**：`env.py` target_metadata=metadata，初始迁移由
  autogenerate 生成（按方言出正确 DDL）；`init_db`=create_all（dev/test 快速路径）。
- **真 Postgres 验证**：`tests/test_postgres_smoke.py` 用 testcontainers 起真 PG16，
  跑通建表 + 会话/消息/工单/时间窗口/token upsert/客服认证全链路。
- **docker-compose**：新增 `postgres` 服务并设为 `api` 默认库（`DB_URL` 可 env 覆盖回
  SQLite）。
- **跨方言 bug（真 PG 测试抓出）**：token 计量的 `ON CONFLICT DO UPDATE` 裸列名在 PG
  上有歧义，已改表名限定（两库通用）。

### 运维切换
1. 生产把 `DB_URL` 指向 Postgres（`postgresql+asyncpg://...`）。
2. 首次部署 `cd server && uv run alembic upgrade head` 建表（或依赖启动 init_db）。
3. 后续 schema 变更：改 `schema.py` → `alembic revision --autogenerate` → review →
   `alembic upgrade head`。

> 仍可回退 SQLite（设 `DB_URL=sqlite+aiosqlite:///...`）；同一套代码两库通用。
> 业务只读库 unlimitpay/nexus 不受影响（仍走 aiomysql / 阿里云 RDS）。
