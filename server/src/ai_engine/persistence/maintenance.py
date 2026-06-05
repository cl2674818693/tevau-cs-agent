"""僵尸回合清理 + 转人工超时事项中心推送：后台 sweep_loop 周期触发。

- reclaim_stale_turns: processing 卡太久的 user 回合标 failed，避免永久挂起。
- push_pending_takeover_timeouts: human_pending 超 sla_policies.take_time 阈值时
  推 pending_takeover_timeout 事件到事项中心，按会话去重（pending_timeout_pushes）。
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from ai_engine.config import settings
from ai_engine.integrations.event_center_client import create_task
from ai_engine.observability import metrics
from ai_engine.persistence import admin_sla, db
from ai_engine.persistence.schema import now_str

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


async def push_pending_takeover_timeouts() -> int:
    """对超 SLA take_time 阈值且未推送过的会话推 pending_takeover_timeout 事件。

    去重表 pending_timeout_pushes 按 conversation_id 主键；推送失败不写表，
    下次扫描可重试，避免事件丢失。返回本次成功推送条数。
    """
    breaches = await admin_sla.compute_breaches()
    take_breaches = [b for b in breaches if b["metric"] == "take_time"]
    if not take_breaches:
        return 0

    pushed_count = 0
    for b in take_breaches:
        cid = int(b["conversation_id"])
        already = await db.fetch_one(
            "SELECT conversation_id FROM pending_timeout_pushes WHERE conversation_id=:cid",
            {"cid": cid},
        )
        if already:
            continue
        conv = await db.fetch_one(
            "SELECT user_type, subject_id, created_at FROM conversations WHERE id=:id",
            {"id": cid},
        )
        if not conv:
            continue
        # 事项中心契约：SLA 升级 → 当成"紧急"新工单推过去，让事项中心分流上级。
        # event_id 用 timeout-{cid}-{threshold} 保证同会话同阈值幂等（重扫不重推）。
        user_type = str(conv["user_type"])
        subject_id = str(conv["subject_id"])
        entity_type = "customer" if user_type == "c" else "partner"
        payload = {
            "event_id": f"timeout-{cid}-{int(b['threshold_seconds'])}",
            "context": (
                f"会话 #{cid}（{user_type} 端 {subject_id}）已等候人工 "
                f"{int(b['elapsed_seconds'])} 秒，超 SLA 阈值 {int(b['threshold_seconds'])} 秒，"
                "请加急分派人工客服接管。"
            ),
            "priority": 4,  # 紧急
            "entities": [{"type": entity_type, "id": subject_id}],
            "source_ref": f"conversation:{cid}",
        }
        ok = await create_task(**payload)
        if not ok:
            continue
        await db.execute(
            "INSERT INTO pending_timeout_pushes(conversation_id, pushed_at, threshold_seconds) "
            "VALUES (:cid, :at, :th)",
            {"cid": cid, "at": now_str(), "th": int(b["threshold_seconds"])},
        )
        pushed_count += 1
        logger.info(
            "pending_takeover_timeout pushed conv=%d elapsed=%ds threshold=%ds",
            cid,
            int(b["elapsed_seconds"]),
            int(b["threshold_seconds"]),
        )
    return pushed_count


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
