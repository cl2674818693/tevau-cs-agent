# Task 1: aiomysql 依赖 + 业务库连接池

> MVP-2 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Modify: `pyproject.toml`（加 aiomysql / asyncmy / testcontainers）
- Modify: `.env.example`（加 UNLIMITPAY_DB_URL / NEXUS_DB_URL）
- Modify: `src/ai_engine/config.py`
- Create: `src/ai_engine/persistence/business_db.py`
- Create: `tests/test_business_db.py`

- [ ] **Step 1: pyproject.toml 加依赖**

```toml
dependencies = [
  # ... 原有 ...
  "aiomysql>=0.2.0",
  "asyncmy>=0.2.10",  # aiomysql 的高性能替代，可选
]

[project.optional-dependencies]
dev = [
  # ... 原有 ...
  "testcontainers[mysql]>=4.7.0",
]
```

- [ ] **Step 2: `.env.example` 追加**

```ini
# 业务只读库（生产用阿里云 RDS，对应 docs/resources.md 的连接信息）
UNLIMITPAY_DB_URL=mysql://tevau_test_read:<password>@<host>:<port>/unlimitpay_test
NEXUS_DB_URL=mysql://nexus_test_read:<password>@<host>:<port>/nexus_test
```

- [ ] **Step 3: `config.py` 加字段**

```python
class Settings(BaseSettings):
    # ... 原有 ...
    unlimitpay_db_url: str | None = None  # MVP-2 必填；MVP-1 测试时为 None
    nexus_db_url: str | None = None
```

- [ ] **Step 4: 写 `tests/test_business_db.py`（先失败）**

```python
import pytest


async def test_business_db_pool_lifecycle(monkeypatch):
    """池能创建、获取连接、关闭。用 sqlite 不行 — 直接断言 API 形态。"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("UNLIMITPAY_DB_URL", "mysql://u:p@h:3306/db")
    from ai_engine.config import settings
    settings.reload()

    from ai_engine.persistence.business_db import BusinessDB
    db = BusinessDB(settings.unlimitpay_db_url)
    assert db.url == "mysql://u:p@h:3306/db"


def test_parse_mysql_url():
    from ai_engine.persistence.business_db import parse_mysql_url
    cfg = parse_mysql_url("mysql://user:pass@host.example:3306/dbname")
    assert cfg == {"user": "user", "password": "pass", "host": "host.example", "port": 3306, "db": "dbname"}


def test_parse_mysql_url_rejects_invalid():
    from ai_engine.persistence.business_db import parse_mysql_url
    with pytest.raises(ValueError):
        parse_mysql_url("postgres://x")
```

- [ ] **Step 5: 跑确认失败**

```bash
pytest tests/test_business_db.py -v
```

- [ ] **Step 6: 写 `src/ai_engine/persistence/business_db.py`**

```python
from dataclasses import dataclass
from urllib.parse import urlparse
import aiomysql


@dataclass
class BusinessDB:
    """一个业务只读库的连接管理器。单例：每个业务库一个实例。"""
    url: str
    _pool: aiomysql.Pool | None = None

    async def ensure_pool(self) -> aiomysql.Pool:
        if self._pool is None:
            cfg = parse_mysql_url(self.url)
            self._pool = await aiomysql.create_pool(
                host=cfg["host"], port=cfg["port"], user=cfg["user"],
                password=cfg["password"], db=cfg["db"], minsize=1, maxsize=10,
                autocommit=True,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        pool = await self.ensure_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")  # 2s 超时兜底
                await cur.execute(sql, params)
                return await cur.fetchone()

    async def fetch_all(self, sql: str, params: tuple = (), limit: int = 100) -> list[dict]:
        pool = await self.ensure_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")
                await cur.execute(sql, params)
                rows = await cur.fetchmany(limit)
                return list(rows or [])


def parse_mysql_url(url: str) -> dict:
    if not url.startswith("mysql://"):
        raise ValueError(f"must start with mysql://, got {url!r}")
    p = urlparse(url)
    return {
        "user": p.username or "",
        "password": p.password or "",
        "host": p.hostname or "",
        "port": p.port or 3306,
        "db": (p.path or "").lstrip("/"),
    }


# 单例池：按需创建，main 启动时填好
_pools: dict[str, BusinessDB] = {}


def get_db(name: str) -> BusinessDB:
    """name ∈ {'unlimitpay', 'nexus'}，运行时由 main 注入 URL。"""
    if name not in _pools:
        raise RuntimeError(f"business db {name!r} not initialized; call init_business_dbs() at startup")
    return _pools[name]


async def init_business_dbs(unlimitpay_url: str | None, nexus_url: str | None) -> None:
    """启动时调一次。MVP-2 上线后 main.py 的 on_startup 触发。"""
    if unlimitpay_url:
        _pools["unlimitpay"] = BusinessDB(unlimitpay_url)
        await _pools["unlimitpay"].ensure_pool()
    if nexus_url:
        _pools["nexus"] = BusinessDB(nexus_url)
        await _pools["nexus"].ensure_pool()


async def close_all() -> None:
    for db in _pools.values():
        await db.close()
    _pools.clear()
```

- [ ] **Step 7: 跑测试**

```bash
pytest tests/test_business_db.py -v
```
Expected: 3 passed

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example src/ai_engine/config.py src/ai_engine/persistence/business_db.py tests/test_business_db.py
git commit -m "feat(mvp-2): aiomysql 业务库连接池（多库分离 + 2s 慢查询兜底）"
```

---
