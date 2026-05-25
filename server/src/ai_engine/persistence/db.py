"""自有库连接层（SQLAlchemy Core / async）。方言无关：sqlite+aiosqlite 或 postgresql+asyncpg。

- engine 按 db_url 缓存（测试每用例切到独立临时库，按 url 各自建 engine）。
- init_db = metadata.create_all（幂等，两库通用），替代原手写 SCHEMA + 丢列风险的 drift 重建。
- 查询走 fetch_one/fetch_all/execute/insert_returning_id helper，返回 dict，消费方零改动。
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


async def insert_returning_id(sql: str, params: dict[str, Any] | None = None) -> int:
    """sql 必须以 RETURNING id 结尾（SQLite>=3.35 与 Postgres 均支持）。"""
    async with _engine().begin() as conn:
        res = await conn.execute(text(sql), params or {})
        return int(res.scalar_one())
