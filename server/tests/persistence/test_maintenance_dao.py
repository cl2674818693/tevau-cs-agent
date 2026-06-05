"""Persistence: maintenance.py — 僵尸回合清理 + 转人工超时事件中心推送。

覆盖：reclaim_stale_turns（cutoff 边界 / 仅 user role / 仅 processing）,
push_pending_takeover_timeouts（SLA breach 触发 / 去重表 / 推送失败不写表 /
推送成功后幂等不重复）, sweep_loop interval<=0 直接退出。

push_event_center 用 monkeypatch 替换，避免真发 HTTP。
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.persistence import (
    admin_sla,
    conversations as conv,
    maintenance,
    staff_metrics as sm,
)
from ai_engine.persistence.db import execute, fetch_all, fetch_one, init_db


@pytest.fixture
async def db_ready(temp_db_url):
    await init_db()
    return temp_db_url


class TestReclaimStaleTurns:
    async def test_marks_old_processing_as_failed(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        # 直接写一条 created_at 早于 cutoff 的 processing user 行
        old = (datetime.now(UTC) - timedelta(seconds=120)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'processing', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.reclaim_stale_turns(timeout_seconds=60)
        assert n == 1
        rows = await conv.list_messages(cid)
        assert rows[0]["status"] == "failed"
        assert rows[0]["error_code"] == "STALE_RECLAIMED"

    async def test_recent_processing_kept(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.append_user_turn(cid, "x", client_message_id=None)
        n = await maintenance.reclaim_stale_turns(timeout_seconds=3600)  # 阈值大 → 不命中
        assert n == 0
        rows = await conv.list_messages(cid)
        assert rows[0]["status"] == "processing"

    async def test_done_rows_untouched(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        tid = await conv.append_user_turn(cid, "x", client_message_id=None)
        await conv.finalize_turn(tid, "done")
        # 即便伪造老时间，done 也不命中（只清 processing）
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE messages SET created_at=:t WHERE id=:id", {"t": old, "id": tid})
        n = await maintenance.reclaim_stale_turns(timeout_seconds=60)
        assert n == 0

    async def test_non_user_role_untouched(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'assistant', 'a', 'processing', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.reclaim_stale_turns(timeout_seconds=60)
        assert n == 0  # 只处理 role='user'

    async def test_no_stale_returns_zero(self, db_ready) -> None:
        assert await maintenance.reclaim_stale_turns(60) == 0


class TestPushPendingTakeoverTimeouts:
    async def test_no_breaches_returns_zero(self, db_ready, monkeypatch) -> None:
        # 无 SLA 策略 → compute_breaches=[]
        async def _push(_p):
            raise AssertionError("should not be called")

        # 契约改造后 maintenance 调 create_task（kwargs 签名），而非旧 push_event_center
        async def _push_kw(**_kwargs):
            return await _push(_kwargs)

        monkeypatch.setattr(maintenance, "create_task", _push_kw)
        assert await maintenance.push_pending_takeover_timeouts() == 0

    async def test_push_success_writes_dedup_row(self, db_ready, monkeypatch) -> None:
        # 1) 准备一个超 SLA 的 human_pending 会话
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid})
        await admin_sla.create_policy("take_time", 60, "all", None)

        pushed = []

        async def _push(payload):
            pushed.append(payload)
            return True

        # 契约改造后 maintenance 调 create_task（kwargs 签名），而非旧 push_event_center
        async def _push_kw(**_kwargs):
            return await _push(_kwargs)

        monkeypatch.setattr(maintenance, "create_task", _push_kw)
        n = await maintenance.push_pending_takeover_timeouts()
        assert n == 1
        # 新契约 payload 字段：event_id / context / priority / entities，不再是旧的 type/conversation_id
        assert pushed[0]["event_id"].startswith(f"timeout-{cid}-")
        assert pushed[0]["priority"] == 4  # SLA 升级走最高优先级
        assert pushed[0]["entities"][0]["id"] == "U1"
        assert pushed[0]["source_ref"] == f"conversation:{cid}"
        # 去重行写入
        row = await fetch_one(
            "SELECT conversation_id, threshold_seconds FROM pending_timeout_pushes "
            "WHERE conversation_id=:c",
            {"c": cid},
        )
        assert row is not None and row["threshold_seconds"] == 60

    async def test_push_idempotent_after_dedup(self, db_ready, monkeypatch) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid})
        await admin_sla.create_policy("take_time", 60, "all", None)

        push_count = 0

        async def _push(_p):
            nonlocal push_count
            push_count += 1
            return True

        # 契约改造后 maintenance 调 create_task（kwargs 签名），而非旧 push_event_center
        async def _push_kw(**_kwargs):
            return await _push(_kwargs)

        monkeypatch.setattr(maintenance, "create_task", _push_kw)
        await maintenance.push_pending_takeover_timeouts()
        await maintenance.push_pending_takeover_timeouts()
        assert push_count == 1  # 第二次因去重表跳过

    async def test_push_failure_no_dedup_write(self, db_ready, monkeypatch) -> None:
        cid = await conv.create_conversation("c", "U1")
        await conv.set_mode(cid, "human_pending")
        old = (datetime.now(UTC) - timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
        await execute("UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid})
        await admin_sla.create_policy("take_time", 60, "all", None)

        async def _push(_p):
            return False

        # 契约改造后 maintenance 调 create_task（kwargs 签名），而非旧 push_event_center
        async def _push_kw(**_kwargs):
            return await _push(_kwargs)

        monkeypatch.setattr(maintenance, "create_task", _push_kw)
        n = await maintenance.push_pending_takeover_timeouts()
        assert n == 0
        # 未写入去重
        rows = await fetch_all(
            "SELECT conversation_id FROM pending_timeout_pushes"
        )
        assert rows == []


class TestSweepLoop:
    async def test_interval_zero_returns_immediately(self, db_ready, monkeypatch) -> None:
        from ai_engine.config import settings as s

        monkeypatch.setattr(s, "stale_sweep_interval_seconds", 0)
        # 不该挂起：interval<=0 立即退出
        await asyncio.wait_for(maintenance.sweep_loop(), timeout=1.0)


class TestArchiveIdleConversations:
    async def test_archives_ai_conversation_with_old_last_message(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 1
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 1

    async def test_keeps_recent_ai_conversation(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U1")
        recent = (datetime.now(UTC) - timedelta(hours=47)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": recent},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_archives_empty_conversation_by_created_at(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U2")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id", {"t": old, "id": cid}
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 1

    async def test_keeps_recent_empty_conversation(self, db_ready) -> None:
        await conv.create_conversation("c", "U2")
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0

    async def test_does_not_archive_non_ai_mode(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U3")
        await execute(
            "UPDATE conversations SET mode='human_takeover' WHERE id=:id", {"id": cid}
        )
        old = (datetime.now(UTC) - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_skips_already_archived(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U4")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        await execute("UPDATE conversations SET archived=1 WHERE id=:id", {"id": cid})
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0

    async def test_hours_zero_disables(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "U5")
        old = (datetime.now(UTC) - timedelta(hours=999)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=0)
        assert n == 0


class TestSweepLoopArchives:
    async def test_sweep_loop_invokes_archive_once(
        self, db_ready, monkeypatch
    ) -> None:
        """sweep_loop 单次迭代会调用 archive_idle_conversations 一次。"""
        from ai_engine.config import settings

        monkeypatch.setattr(settings, "stale_sweep_interval_seconds", 60)
        monkeypatch.setattr(settings, "idle_conversation_archive_hours", 48)

        calls: list[int] = []

        async def _fake_archive(hours: int) -> int:
            calls.append(hours)
            raise asyncio.CancelledError

        monkeypatch.setattr(maintenance, "archive_idle_conversations", _fake_archive)

        async def _noop_reclaim(*_a, **_k) -> int:
            return 0

        async def _noop_push() -> int:
            return 0

        monkeypatch.setattr(maintenance, "reclaim_stale_turns", _noop_reclaim)
        monkeypatch.setattr(maintenance, "push_pending_takeover_timeouts", _noop_push)

        with pytest.raises(asyncio.CancelledError):
            await maintenance.sweep_loop()
        assert calls == [48]


class TestArchiveIdleEdgeCases:
    async def test_max_of_messages_not_first_or_last(self, db_ready) -> None:
        # 同一会话两条消息：老的 100h、新的 47h。COALESCE(MAX, ...) 应取 47h，未到 48h，不归档。
        cid = await conv.create_conversation("c", "EDGE1")
        very_old = (datetime.now(UTC) - timedelta(hours=100)).strftime("%Y-%m-%d %H:%M:%S")
        recent = (datetime.now(UTC) - timedelta(hours=47)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'old', 'done', :t)",
            {"cid": cid, "t": very_old},
        )
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'assistant', 'new', 'done', :t)",
            {"cid": cid, "t": recent},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_does_not_archive_human_pending_mode(self, db_ready) -> None:
        # human_takeover 已被现有测试覆盖；这里补 human_pending 同样不归档。
        cid = await conv.create_conversation("c", "EDGE2")
        await execute(
            "UPDATE conversations SET mode='human_pending' WHERE id=:id", {"id": cid}
        )
        old = (datetime.now(UTC) - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'hi', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 0
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_mixed_batch_only_qualifying_archived(self, db_ready) -> None:
        # 一次 sweep 内：合规归档 / 非到期 / 非 ai / 已归档 共存，期望只有 1 个被归档。
        ai_old = await conv.create_conversation("c", "BATCH_A")
        ai_recent = await conv.create_conversation("c", "BATCH_B")
        human_old = await conv.create_conversation("c", "BATCH_C")
        ai_already = await conv.create_conversation("c", "BATCH_D")

        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        recent = (datetime.now(UTC) - timedelta(hours=47)).strftime("%Y-%m-%d %H:%M:%S")
        very_old = (datetime.now(UTC) - timedelta(hours=72)).strftime("%Y-%m-%d %H:%M:%S")

        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": ai_old, "t": old},
        )
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": ai_recent, "t": recent},
        )
        await execute(
            "UPDATE conversations SET mode='human_takeover' WHERE id=:id", {"id": human_old}
        )
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": human_old, "t": very_old},
        )
        await execute("UPDATE conversations SET archived=1 WHERE id=:id", {"id": ai_already})
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": ai_already, "t": old},
        )

        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 1

        rows = await fetch_all(
            "SELECT id, archived FROM conversations WHERE id IN (:a, :b, :c, :d) ORDER BY id",
            {"a": ai_old, "b": ai_recent, "c": human_old, "d": ai_already},
        )
        by_id = {int(r["id"]): int(r["archived"]) for r in rows}
        assert by_id[ai_old] == 1
        assert by_id[ai_recent] == 0
        assert by_id[human_old] == 0
        assert by_id[ai_already] == 1  # 一直是 1，未被改回

    async def test_archives_all_qualifying_in_one_sweep(self, db_ready) -> None:
        # 5 个老 AI 会话同时存在，期望一次 sweep 全部 archived=1。
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(5):
            cid = await conv.create_conversation("c", f"MANY{i}")
            await execute(
                "INSERT INTO messages(conversation_id, role, content, status, created_at) "
                "VALUES (:cid, 'user', 'x', 'done', :t)",
                {"cid": cid, "t": old},
            )

        n = await maintenance.archive_idle_conversations(hours=48)
        assert n == 5
        rows = await fetch_all(
            "SELECT archived FROM conversations WHERE subject_id LIKE :p",
            {"p": "MANY%"},
        )
        assert len(rows) == 5
        assert all(int(r["archived"]) == 1 for r in rows)

    async def test_cutoff_strict_less_than(self, db_ready) -> None:
        # HAVING 使用 `<` 严格小于。若最后消息时间正好等于 cutoff，不该归档。
        # 我们覆写 datetime.now：固定它，使函数算出的 cutoff 与 message.created_at 完全相等。
        fixed_now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)
        cutoff_str = (fixed_now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        cid = await conv.create_conversation("c", "BOUND")
        # 让 conversations.created_at 也早于 cutoff（避免空-conv 兜底干扰）
        await execute(
            "UPDATE conversations SET created_at=:t WHERE id=:id",
            {"t": cutoff_str, "id": cid},
        )
        # 最后消息恰好 = cutoff
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": cid, "t": cutoff_str},
        )

        class _FixedDT:
            @staticmethod
            def now(_tz=None):
                return fixed_now

        # 只 patch maintenance.datetime（函数从此模块取）
        import ai_engine.persistence.maintenance as _m

        original = _m.datetime
        _m.datetime = _FixedDT  # type: ignore[assignment]
        try:
            n = await maintenance.archive_idle_conversations(hours=48)
        finally:
            _m.datetime = original
        assert n == 0  # 相等不归档（严格 <）
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        assert row["archived"] == 0

    async def test_negative_hours_disables(self, db_ready) -> None:
        cid = await conv.create_conversation("c", "NEG")
        old = (datetime.now(UTC) - timedelta(hours=999)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'x', 'done', :t)",
            {"cid": cid, "t": old},
        )
        n = await maintenance.archive_idle_conversations(hours=-1)
        assert n == 0

    async def test_default_settings_is_48(self) -> None:
        # 真实读 settings 验证默认值（不 monkeypatch）。
        from ai_engine.config import settings as s

        assert s.idle_conversation_archive_hours == 48

    async def test_race_user_replies_in_select_to_update_window(
        self, db_ready, monkeypatch
    ) -> None:
        """SELECT→UPDATE 窗口内用户发了新消息，UPDATE 应复算 last_msg 并跳过该 conv。

        模拟方式：monkeypatch db.execute，在第一次 UPDATE 之前插入一条"刚发的新消息"。
        没有 race-guard 时，函数仍归档；有 guard 时，跳过 → n==1 但该 conv archived 仍为 0。
        """
        cid = await conv.create_conversation("c", "RACE")
        old = (datetime.now(UTC) - timedelta(hours=49)).strftime("%Y-%m-%d %H:%M:%S")
        await execute(
            "INSERT INTO messages(conversation_id, role, content, status, created_at) "
            "VALUES (:cid, 'user', 'old', 'done', :t)",
            {"cid": cid, "t": old},
        )

        # 在 archive 的 SELECT 之后、UPDATE 之前插入新消息
        import ai_engine.persistence.maintenance as _m

        original_execute = _m.db.execute
        injected = {"done": False}

        async def _wrapped_execute(sql: str, params: dict | None = None):
            if not injected["done"] and sql.startswith("UPDATE conversations SET archived"):
                now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
                await original_execute(
                    "INSERT INTO messages(conversation_id, role, content, status, created_at) "
                    "VALUES (:cid, 'user', 'fresh', 'done', :t)",
                    {"cid": cid, "t": now_str},
                )
                injected["done"] = True
            return await original_execute(sql, params)

        monkeypatch.setattr(_m.db, "execute", _wrapped_execute)

        await maintenance.archive_idle_conversations(hours=48)
        row = await fetch_one("SELECT archived FROM conversations WHERE id=:id", {"id": cid})
        # 期望：race guard 生效，archived 仍为 0；用户刚发的新消息留在活跃会话
        assert row["archived"] == 0, (
            "Race condition: SELECT→UPDATE 窗口内用户发了新消息，"
            "UPDATE 仍然归档了会话；该会话变成不可续接的 archived，丢失刚发的消息"
        )
