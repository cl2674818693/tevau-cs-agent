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
                charset="utf8mb4",  # 否则中文字段（如 lock_reason）乱码
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def _exec_with_retry(self, runner):  # noqa: ANN001
        """跑一次查询；若拿到的 connection 已被 RDS 服务端关闭（典型 OperationalError 2013
        "Lost connection during query" 或 2006 "MySQL server has gone away"），丢弃该 conn
        重新 acquire 一次。aiomysql 没有 pool_pre_ping，pool 长时间 idle 后第一次复用必死，
        靠这一层 try-once 保活，避免业务请求被瞬态连接断击穿。

        注意：ping 失败或 OperationalError 时强制 conn.close()，让 pool 丢弃这个坏 conn；
        普通成功路径走 pool.release()，conn 仍可复用。
        """
        pool = await self.ensure_pool()
        last_err: Exception | None = None
        for attempt in range(2):
            conn = await pool.acquire()
            released = False
            try:
                # aiomysql 的 conn.ping(reconnect=True) 检测连接是否还活，必要时静默重连；
                # 比"先跑 SQL 再捕异常"更便宜（ping 单次 ~1ms vs 失败查询往返 + 异常栈）
                try:
                    await conn.ping(reconnect=True)
                except Exception as ping_err:
                    last_err = ping_err
                    conn.close()  # 强制丢弃损坏 conn，pool 不会复用
                    released = True
                    if attempt == 0:
                        continue
                    raise
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    return await runner(cur)
            except aiomysql.OperationalError as e:
                # 2013/2006/2003 都是 connection 层错误：丢弃 conn + 重试一次
                last_err = e
                if e.args and e.args[0] in (2013, 2006, 2003):
                    conn.close()
                    released = True
                    if attempt == 0:
                        continue
                raise
            finally:
                if not released:
                    pool.release(conn)
        raise last_err if last_err else RuntimeError("unreachable")

    async def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        async def _run(cur):  # noqa: ANN001
            await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")  # 2s 慢查询兜底
            await cur.execute(sql, params)
            row = await cur.fetchone()
            return dict(row) if row else None
        return await self._exec_with_retry(_run)

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] = (), limit: int = 100
    ) -> list[dict[str, Any]]:
        async def _run(cur):  # noqa: ANN001
            await cur.execute("SET SESSION MAX_EXECUTION_TIME=2000")
            await cur.execute(sql, params)
            rows = await cur.fetchmany(limit)
            return [dict(r) for r in (rows or [])]
        return await self._exec_with_retry(_run)


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
