from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import aiomysql


def parse_mysql_url(url: str) -> dict[str, Any]:
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


@dataclass
class BusinessDB:
    """一个业务只读库的连接管理器。单例：每个业务库一个实例（spec §5.5）。"""

    url: str
    _pool: Any = None

    async def ensure_pool(self) -> Any:
        if self._pool is None:
            cfg = parse_mysql_url(self.url)
            self._pool = await aiomysql.create_pool(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                db=cfg["db"],
                minsize=1,
                maxsize=10,
                autocommit=True,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        pool = await self.ensure_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")  # 2s 慢查询兜底
            await cur.execute(sql, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = (), limit: int = 100
    ) -> list[dict[str, Any]]:
        pool = await self.ensure_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")
            await cur.execute(sql, params)
            rows = await cur.fetchmany(limit)
            return [dict(r) for r in (rows or [])]


_pools: dict[str, BusinessDB] = {}


def get_db(name: str) -> BusinessDB:
    """name ∈ {'unlimitpay', 'nexus'}；运行时由 main 注入 URL。"""
    if name not in _pools:
        raise RuntimeError(
            f"business db {name!r} not initialized; call init_business_dbs() at startup"
        )
    return _pools[name]


async def init_business_dbs(unlimitpay_url: str | None, nexus_url: str | None) -> None:
    """启动时调一次（main.py on_startup）。"""
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
