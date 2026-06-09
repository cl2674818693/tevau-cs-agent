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


async def reclaim_zombie_takeovers(staff_idle_seconds: int = 300) -> list[int]:
    """F-P0-4 / B-P1: 客服掉线后 mode=human_takeover 卡死的会话自动释放回 AI。

    条件：会话 mode=human_takeover 且 assigned_staff_id 对应的 staff 满足之一：
    - 无 staff_presence 行（从未发心跳，等同已离线）；
    - staff_presence.last_seen_at 早于 now - staff_idle_seconds（心跳超时）；
    - staff_presence.status='offline'（显式下线但未 release）。

    释放后 mode=ai + assigned_staff_id=NULL。返回被释放的 conv_id 列表，调用方按需推
    mode_change 事件。SQLite/PG 通用语法（不依赖 UPDATE...RETURNING）。
    """
    cutoff = (datetime.now(UTC) - timedelta(seconds=staff_idle_seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    # 找出所有当前 human_takeover 但 staff 已离线/超时/无心跳的会话
    rows = await db.fetch_all(
        "SELECT c.id FROM conversations c "
        "LEFT JOIN staff_presence sp ON sp.staff_id = c.assigned_staff_id "
        "WHERE c.mode='human_takeover' AND c.assigned_staff_id IS NOT NULL "
        "AND (sp.staff_id IS NULL "
        "  OR sp.status='offline' "
        "  OR sp.last_seen_at < :cutoff)",
        {"cutoff": cutoff},
    )
    ids = [int(r["id"]) for r in rows]
    if not ids:
        return []
    placeholders = ",".join(f":id{i}" for i in range(len(ids)))
    params: dict[str, object] = {f"id{i}": v for i, v in enumerate(ids)}
    await db.execute(
        f"UPDATE conversations SET mode='ai', assigned_staff_id=NULL, assigned_at=NULL "
        f"WHERE id IN ({placeholders}) AND mode='human_takeover'",
        params,
    )
    logger.warning(
        "reclaimed %d zombie takeovers (idle_seconds=%d)", len(ids), staff_idle_seconds
    )
    return ids


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
    """归档 mode='ai' 且空闲超 hours 小时的会话，返回 SELECT 出的候选条数。

    空闲判定：COALESCE(MAX(messages.created_at), conversations.created_at) < cutoff，
    即按"最后一条消息时间"算；空会话用 conversations.created_at 兜底。
    只动 mode='ai'：转人工态(human_pending/human_takeover)可能仍在客服 follow-up 中，
    归档会让 C 端用户回来时接不上原客服。hours<=0 时直接返回 0（开关禁用）。

    Race-guard：UPDATE 时带 NOT EXISTS(... created_at >= cutoff) 复算，避免
    SELECT→UPDATE 窗口内用户回来发新消息却仍被归档（会丢失刚发的消息）。
    返回的是 SELECT 候选数；个别 conv 因 race-guard 被跳过时实际状态以 archived 列为准。
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
            "UPDATE conversations SET archived = 1 "
            "WHERE id = :id AND COALESCE(archived, 0) = 0 "
            "AND NOT EXISTS ("
            "SELECT 1 FROM messages "
            "WHERE conversation_id = :id AND created_at >= :cutoff"
            ")",
            {"id": int(r["id"]), "cutoff": cutoff},
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
        # B-P1-3: 并发 sweeper race —— A SELECT 没有 → A push → 期间 B 已 INSERT 占位 →
        # A 自己 INSERT 必须静默跳过（事项中心已用 event_id 幂等去重，重复 push 无副作用；
        # 这里仅防主键冲突让 sweep 协程崩掉）。SQLite ON CONFLICT DO NOTHING / MySQL INSERT IGNORE。
        if db.dialect_name() == "mysql":
            sql = (
                "INSERT IGNORE INTO pending_timeout_pushes(conversation_id, pushed_at, threshold_seconds) "
                "VALUES (:cid, :at, :th)"
            )
        else:
            sql = (
                "INSERT INTO pending_timeout_pushes(conversation_id, pushed_at, threshold_seconds) "
                "VALUES (:cid, :at, :th) "
                "ON CONFLICT(conversation_id) DO NOTHING"
            )
        await db.execute(
            sql,
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
            released = await reclaim_zombie_takeovers(
                staff_idle_seconds=settings.staff_idle_release_seconds
            )
            # F-P0-4: 释放后推 mode_change 让旁观/前端立刻刷新
            if released:
                from ai_engine.api.staff_conversations import _publish  # lazy import 避免循环

                for cid in released:
                    _publish(cid, {"type": "mode_change", "to": "ai", "reason": "staff_idle_timeout"})
        except Exception:
            logger.exception("zombie takeover reclaim failed")
        try:
            await push_pending_takeover_timeouts()
        except Exception:
            logger.exception("pending takeover timeout sweep failed")
        try:
            await archive_idle_conversations(settings.idle_conversation_archive_hours)
        except Exception:
            logger.exception("idle conversation archive sweep failed")
        await asyncio.sleep(interval)
