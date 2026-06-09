"""自有库连接层（SQLAlchemy Core / async）。方言无关：sqlite+aiosqlite 或 mysql+aiomysql。

- engine 按 db_url 缓存（测试每用例切到独立临时库，按 url 各自建 engine）。
- init_db = metadata.create_all（幂等，两库通用），替代原手写 SCHEMA + 丢列风险的 drift 重建。
- 查询走 fetch_one/fetch_all/execute/insert_returning_id helper，返回 dict，消费方零改动。
- 2026-06 公司统一 MySQL，下线 Postgres 支持：insert_returning_id 改用 cursor.lastrowid；
  ON CONFLICT 在 4 处 UPSERT 用方言分发字符串（SQLite 保留原语法 dev/test 用，MySQL 出 ON DUPLICATE KEY UPDATE）。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from ai_engine.config import settings
from ai_engine.persistence.schema import metadata

_engines: dict[str, AsyncEngine] = {}


def _engine() -> AsyncEngine:
    url = settings.db_url
    eng = _engines.get(url)
    if eng is None:
        eng = create_async_engine(url, future=True)
        _engines[url] = eng
    return eng


def _path_from_url(url: str) -> str:
    """从 sqlite URL 取文件路径（测试做文件级断言用）。"""
    return url.replace("sqlite+aiosqlite:///", "", 1)


async def init_db() -> None:
    # sqlite 文件库需先建父目录
    url = settings.db_url
    if url.startswith("sqlite"):
        Path(_path_from_url(url)).parent.mkdir(parents=True, exist_ok=True)
    async with _engine().begin() as conn:
        await conn.run_sync(metadata.create_all)


@asynccontextmanager
async def get_conn() -> AsyncIterator[AsyncConnection]:
    """事务性连接（退出即提交）。直接执行 SQL 时用 text() + 命名参数。"""
    async with _engine().begin() as conn:
        yield conn


async def fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    async with _engine().connect() as conn:
        res = await conn.execute(text(sql), params or {})
        row = res.mappings().first()
        return dict(row) if row else None


async def fetch_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    async with _engine().connect() as conn:
        res = await conn.execute(text(sql), params or {})
        return [dict(r) for r in res.mappings().all()]


async def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    async with _engine().begin() as conn:
        await conn.execute(text(sql), params or {})


async def execute_rowcount(sql: str, params: dict[str, Any] | None = None) -> int:
    """执行 UPDATE/DELETE 并返回受影响行数（用于 404 判定）。"""
    async with _engine().begin() as conn:
        res = await conn.execute(text(sql), params or {})
        return int(res.rowcount or 0)


async def insert_returning_id(sql: str, params: dict[str, Any] | None = None) -> int:
    """INSERT 并返回自增 id（cursor.lastrowid）。MySQL / SQLite 通用。

    历史遗留：SQL 字符串如果尾部带 RETURNING id（旧 PG/SQLite 写法）会被自动剥离，
    实际靠 DBAPI 的 cursor.lastrowid（aiomysql/aiosqlite 均支持）拿自增 id。
    """
    cleaned = sql.rsplit("RETURNING", 1)[0].rstrip().rstrip(",")
    async with _engine().begin() as conn:
        res = await conn.execute(text(cleaned), params or {})
        return int(res.lastrowid)


def dialect_name() -> str:
    """当前 engine 的方言名（'sqlite' / 'mysql' / ...）。UPSERT 等方言分发处用。"""
    return _engine().dialect.name
