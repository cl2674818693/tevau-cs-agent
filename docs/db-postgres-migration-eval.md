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
> 因用原生 SQL 模式（`target_metadata=None`），`--autogenerate` 不可用，迁移手写。

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

### 结论与建议
- **本轮已解决最高风险点**：用 alembic 版本化迁移替代"就地重建丢列"。
- **是否立即迁 Postgres**：取决于自有库的并发写量与多副本部署需求。若近期单副本、
  写量不大，SQLite + alembic 可继续；**一旦要多副本或写量上来，必须迁 Postgres**。
- **迁移真正的成本不在 DDL，而在 persistence 层散落的原生 SQL**。建议先做
  SQLAlchemy Core 收敛（可独立成一个 reviewed 的重构 PR），再切库，风险最低。
- 这一步是较大的持久层重构，**不宜与本轮可靠性加固混在一起**，单独立项执行。
