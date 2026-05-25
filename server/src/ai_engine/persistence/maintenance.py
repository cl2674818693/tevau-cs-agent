"""僵尸回合清理：把 processing 卡太久的 user 回合标 failed，避免永久挂起。

触发场景：服务进程在 agent loop 中途崩溃/被 kill，回合 status 永远停在 processing。
后台 sweep_loop 周期扫描；reclaim_stale_turns 也可被单元测试/手动调用。
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from ai_engine.config import settings
from ai_engine.observability import metrics
from ai_engine.persistence import db

logger = logging.getLogger(__name__)


async def reclaim_stale_turns(timeout_seconds: int) -> int:
    """把 status=processing 且 created_at 早于 cutoff 的 user 回合标 failed，返回清理条数。"""
    cutoff = (datetime.now(UTC) - timedelta(seconds=timeout_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    rows = await db.fetch_all(
        "SELECT id FROM messages WHERE role='user' AND status='processing' AND created_at < :c",
        {"c": cutoff},
    )
    if not rows:
        return 0
    await db.execute(
        "UPDATE messages SET status='failed', error_code='STALE_RECLAIMED' "
        "WHERE role='user' AND status='processing' AND created_at < :c",
        {"c": cutoff},
    )
    n = len(rows)
    metrics.stale_turns_reclaimed_total.inc(n)
    logger.warning("reclaimed %d stale turns (cutoff=%s)", n, cutoff)
    return n


async def sweep_loop() -> None:
    """后台周期清理。interval<=0 时立即退出（关闭）。"""
    interval = settings.stale_sweep_interval_seconds
    if interval <= 0:
        return
    while True:
        try:
            await reclaim_stale_turns(settings.stale_turn_timeout_seconds)
        except Exception:
            logger.exception("stale sweep iteration failed")
        await asyncio.sleep(interval)
